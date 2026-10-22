import base64
import datetime
import hashlib
import json
import logging
import re

import xlrd
from openai import APIStatusError, NotFoundError, OpenAI

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.addons.base.models.res_bank import sanitize_account_number
from odoo.addons.gn_qif_openai_reconcile.models import gn_qif_bank_xlsx, gn_qif_parser, gn_qif_pdf_occident
from odoo.tools.mail import html2plaintext

logger = logging.getLogger(__name__)

# Valor seguro por defecto; el id debe existir en la API para su clave (platform.openai.com/docs/models).
DEFAULT_OPENAI_MODEL = 'gpt-4.1-mini'

_CURRENCY_HINTS = frozenset({
    'USD', 'EUR', 'GTQ', 'MXN', 'CRC', 'HNL', 'NIO', 'PAB', 'DOP', 'COP', 'CLP', 'PEN', 'BOB', 'PYG', 'UYU', 'ARS', 'BRL', 'CAD', 'GBP', 'CHF', 'JPY', 'CNY',
})


def _extract_heuristic_qif_metadata(text):
    """Extrae cabeceras no estándar (!Account, !Bank, etc.) del texto QIF."""
    meta = {'bank': '', 'account': '', 'currency': ''}
    for line in text.splitlines()[:500]:
        line = line.strip()
        if not line:
            continue
        ul = line.upper()
        if ul.startswith('!ACCOUNT'):
            rest = line.split(':', 1)[-1].strip() if ':' in line else line[8:].strip()
            if rest:
                meta['account'] = rest[:256]
        elif ul.startswith('!BANKNAME') or ul.startswith('!BANK'):
            rest = line.split(':', 1)[-1].strip()
            if not rest and ul.startswith('!BANKNAME'):
                rest = line[9:].strip()
            elif not rest and ul.startswith('!BANK'):
                rest = line[5:].strip()
            if rest:
                meta['bank'] = rest[:256]
    m = re.search(
        r'\b(' + '|'.join(sorted(_CURRENCY_HINTS, key=len, reverse=True)) + r')\b',
        text[:12000], re.I,
    )
    if m:
        meta['currency'] = m.group(1).upper()
    return meta


def _parse_ficohsa_xls(raw_bytes):
    """Parse FICOHSA bank statement from XLS format.

    Returns (transactions, metadata) in the same structure as _parse_qif_raw.
    The FICOHSA XLS has a fixed layout:
      Row 3:  Titular
      Row 6:  Cuenta #, Alias
      Row 13: Date range
      Row 15: Saldo inicial / final
      Row 16: Column headers (Fecha, Descripción, …, Débito, Crédito, …, Balance)
      Row 17+: Transaction rows
    """
    try:
        wb = xlrd.open_workbook(file_contents=raw_bytes)
    except xlrd.XLRDError as e:
        raise UserError(_('No se pudo abrir el archivo XLS: %s') % e)

    sh = wb.sheet_by_index(0)

    def _cell(r, c):
        if r >= sh.nrows or c >= sh.ncols:
            return ''
        cell = sh.cell(r, c)
        if cell.ctype == xlrd.XL_CELL_DATE:
            dt = xlrd.xldate_as_tuple(cell.value, wb.datemode)
            return f'{dt[2]:02d}/{dt[1]:02d}/{dt[0]}'
        if cell.ctype == xlrd.XL_CELL_NUMBER:
            return str(cell.value)
        return (cell.value or '').strip().strip("'")

    def _parse_amount(text):
        text = (text or '').strip().strip("'")
        if not text:
            return 0.0
        return float(text.replace(',', ''))

    titular = ''
    account_number = ''
    alias = ''
    balance_start = 0.0
    balance_end = 0.0
    date_range_text = ''

    for r in range(min(20, sh.nrows)):
        val = _cell(r, 1)
        if val.startswith('Titular:'):
            titular = val.split(':', 1)[1].strip()
        elif val == 'Cuenta #':
            account_number = _cell(r + 1, 1) if r + 1 < sh.nrows else ''
            alias = _cell(r + 1, 3) if r + 1 < sh.nrows else ''
        elif re.match(r'\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}', val):
            date_range_text = val
        elif val.startswith('Saldo inicial:'):
            m = re.findall(r'[\d,]+\.\d{2}', val)
            if len(m) >= 2:
                balance_start = _parse_amount(m[0])
                balance_end = _parse_amount(m[1])
            elif len(m) == 1:
                balance_start = _parse_amount(m[0])

    header_row = None
    for r in range(min(25, sh.nrows)):
        if _cell(r, 1) == 'Fecha' and 'Descripci' in _cell(r, 2):
            header_row = r
            break
    if header_row is None:
        raise UserError(_('No se encontró la fila de encabezados en el archivo FICOHSA XLS.'))

    transactions = []
    dates = []
    total_amount = 0.0
    for r in range(header_row + 1, sh.nrows):
        date_str = _cell(r, 1)
        if not date_str or not re.match(r'\d{2}/\d{2}/\d{4}', date_str):
            continue
        description = _cell(r, 2)
        check_num = _cell(r, 4)
        debit = _parse_amount(_cell(r, 5))
        credit = _parse_amount(_cell(r, 6))
        amount = credit - debit

        try:
            dt = datetime.datetime.strptime(date_str, '%d/%m/%Y').date()
        except ValueError:
            continue

        dates.append(dt)
        total_amount += amount
        transactions.append({
            'date': dt,
            'amount': amount,
            'payment_ref': description,
            'ref': check_num if check_num else '',
            'sequence': len(transactions) + 1,
        })

    metadata = {
        'min_date': min(dates) if dates else None,
        'max_date': max(dates) if dates else None,
        'total_amount': total_amount,
        'count': len(transactions),
        'balance_start': balance_start,
        'balance_end': balance_end,
        'titular': titular,
        'account_number': account_number,
        'alias': alias,
        'bank_name': 'FICOHSA',
        'currency': 'HNL',
    }
    return transactions, metadata


def _davivienda_hn_header_row(sh):
    """Índice de fila de encabezado Davivienda HN (Fecha col A …) o None."""
    for r in range(min(45, sh.nrows)):
        if sh.ncols < 6:
            break
        c0 = str(sh.cell_value(r, 0)).strip().lower()
        c1 = str(sh.cell_value(r, 1)).strip().lower()
        if c0 != "fecha" or "descri" not in c1:
            continue
        c2 = str(sh.cell_value(r, 2)).strip().lower()
        c3 = str(sh.cell_value(r, 3)).strip().lower()
        c4 = str(sh.cell_value(r, 4)).strip().lower()
        if (
            ("débit" in c2 or "debit" in c2)
            and ("crédit" in c3 or "credit" in c3)
            and ("saldo" in c4 or "balance" in c4)
        ):
            return r
    return None


def _parse_davivienda_hn_xls(raw_bytes):
    """Extracto típico Banco Davivienda Honduras (CSV/XLS texto). Importe = crédito − débito."""
    try:
        wb = xlrd.open_workbook(file_contents=raw_bytes)
    except xlrd.XLRDError as e:
        raise UserError(_("No se pudo abrir el archivo XLS: %s") % e)

    sh = wb.sheet_by_index(0)

    def _cell(r, c):
        if r >= sh.nrows or c >= sh.ncols:
            return ""
        cell = sh.cell(r, c)
        if cell.ctype == xlrd.XL_CELL_DATE:
            dt_tuple = xlrd.xldate_as_tuple(cell.value, wb.datemode)
            return f"{dt_tuple[2]:02d}/{dt_tuple[1]:02d}/{dt_tuple[0]}"
        if cell.ctype == xlrd.XL_CELL_NUMBER:
            return str(cell.value)
        return (cell.value or "").strip().strip("'")

    def _parse_amount(text):
        t = (text or "").strip().strip("'").replace(",", "")
        if not t:
            return 0.0
        return float(t)

    header_row = _davivienda_hn_header_row(sh)
    if header_row is None:
        raise UserError(_("No se encontró la tabla de movimientos (formato Davivienda Honduras)."))

    titular = ""
    account_number = ""
    currency = "HNL"
    for r in range(header_row):
        val = _cell(r, 0)
        lv = val.lower()
        if val.startswith("Cliente:"):
            titular = val.split(":", 1)[1].strip()
        if "cuenta:" in lv and ("corriente" in lv or "davivienda" in lv):
            digits_m = re.search(r"(\d{8,})", val)
            if digits_m:
                account_number = digits_m.group(1)
            if "lps" in val.upper() or "lempira" in lv:
                currency = "HNL"

    transactions = []
    dates = []
    total_amount = 0.0
    for r in range(header_row + 1, sh.nrows):
        date_str = _cell(r, 0)
        if not date_str or not re.match(r"\d{2}/\d{2}/\d{4}", date_str):
            continue
        description = _cell(r, 1)
        debit = _parse_amount(_cell(r, 2))
        credit = _parse_amount(_cell(r, 3))
        saldo = _parse_amount(_cell(r, 4)) if sh.ncols > 4 else 0.0
        amount = credit - debit
        ref = _cell(r, 5) if sh.ncols > 5 else ""
        tail = (_cell(r, 6).strip() if sh.ncols > 6 else "")
        payment = description + ((". " + tail) if tail and tail != description else "")

        try:
            dt_v = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            continue

        dates.append(dt_v)
        total_amount += amount
        transactions.append({
            "date": dt_v,
            "amount": amount,
            "payment_ref": payment or _("Sin descripción"),
            "ref": (ref[:256] if ref else ""),
            "sequence": len(transactions) + 1,
            "_saldo_after": saldo,
        })

    if not transactions:
        raise UserError(_("No hay filas de movimiento con fecha válida en el XLS Davivienda."))

    chron = sorted(transactions, key=lambda t: (t["date"], t["sequence"]))
    balance_start = chron[0]["_saldo_after"] - chron[0]["amount"] if chron else 0.0
    balance_end = chron[-1]["_saldo_after"] if chron else 0.0
    for t in transactions:
        t.pop("_saldo_after", None)

    metadata = {
        "min_date": min(dates),
        "max_date": max(dates),
        "total_amount": total_amount,
        "count": len(transactions),
        "balance_start": balance_start,
        "balance_end": balance_end,
        "titular": titular[:256],
        "account_number": account_number[:64],
        "alias": "",
        "bank_name": _("Banco Davivienda Honduras"),
        "currency": currency,
    }
    return transactions, metadata


class QifAiWizard(models.TransientModel):
    _name = 'qif.ai.wizard'
    _description = 'Análisis QIF con IA'

    journal_id = fields.Many2one(
        'account.journal', string='Diario destino (Odoo)',
        domain="[('type', 'in', ('bank', 'cash'))]",
        help='Opcional para analizar. Obligatorio para importar o crear modelos en un diario concreto.',
    )
    qif_file = fields.Binary('Estado de cuenta', required=True)
    qif_filename = fields.Char('Nombre del archivo')
    file_format = fields.Selection([
        ('qif', 'QIF'),
        ('xls_ficohsa', 'XLS (FICOHSA)'),
        ('xls_davivienda_hn', 'XLS (Davivienda HN)'),
        ('pdf_occident', 'PDF (extracto Honduras / Occidente)'),
        ('xlsx_atlantida', 'Excel (.xlsx) Banco Atlántida'),
        ('xlsx_banpais', 'Excel (.xlsx) Banpaís'),
        ('xlsx_occidente_hn', 'Excel (.xlsx) Banco Occidente HN'),
        ('unknown', 'Desconocido'),
    ], string='Formato detectado', readonly=True, default='unknown')
    date_from = fields.Date('Desde')
    date_to = fields.Date('Hasta')
    qif_line_count = fields.Integer('Transacciones en archivo', readonly=True)
    qif_balance_start = fields.Float(
        'Saldo inicial (derivado)', digits=(16, 2), readonly=True,
        help='Calculado como 0 para archivos QIF que no traen saldo bancario real.',
    )
    qif_balance_end = fields.Float(
        'Saldo final (suma movimientos)', digits=(16, 2), readonly=True,
        help='Suma de todos los importes del archivo QIF. '
             'El formato QIF no incluye el saldo real del banco.',
    )
    file_bank_name = fields.Char(
        string='Banco (detectado en archivo)',
        readonly=True,
        help='Inferido desde cabeceras QIF y/o IA. No es el diario configurado en Odoo.',
    )
    file_account_name = fields.Char(
        string='Cuenta (detectada en archivo)',
        readonly=True,
        help='Nombre de cuenta o máscara inferida del extracto.',
    )
    file_currency_code = fields.Char(
        string='Moneda (detectada)',
        readonly=True,
        help='Código ISO si se encontró en el texto o movimientos.',
    )
    file_company_hint = fields.Char(
        string='Empresa / titular (pista)',
        readonly=True,
        help='Pista de nombre de empresa o titular si aparece en el extracto; no sustituye a la compañía Odoo.',
    )
    file_meta_confidence = fields.Float(
        string='Confianza metadatos', digits=(3, 2), readonly=True,
    )
    file_meta_source = fields.Selection([
        ('none', 'Sin datos'),
        ('heuristic', 'Cabeceras QIF'),
        ('ai', 'Inferencia IA'),
        ('hybrid', 'Cabeceras + IA'),
    ], string='Origen metadatos', readonly=True, default='none')
    file_meta_evidence = fields.Text(
        string='Evidencia',
        readonly=True,
        help='Breve justificación o fragmento usado para inferir banco/cuenta.',
    )
    odoo_journal_bank_name = fields.Char(
        related='journal_id.bank_id.name', string='Banco (config. Odoo)', readonly=True,
    )
    odoo_journal_account_number = fields.Char(
        related='journal_id.bank_account_id.acc_number',
        string='Cuenta (config. Odoo)', readonly=True,
    )
    ai_summary_brief = fields.Text(
        string='Resumen de sugerencias',
        readonly=True,
        help='Resumen de la última ejecución del análisis.',
    )
    allow_reimport = fields.Boolean(
        'Permitir reimportar este archivo', default=False,
        help='Active esta opción si necesita volver a importar un archivo QIF '
             'que ya consta en el historial (p. ej. tras borrar extractos para '
             'reconstruir el mes). Las líneas cuyo identificador único ya exista '
             'en Odoo seguirán siendo omitidas automáticamente.',
    )
    auto_promote_reconcile_ce = fields.Boolean(
        string='Registrar y crear «modelos de conciliación» Odoo tras análisis IA',
        default=False,
        help='Registra cada patrón por diario/formato en «Patrones aprendidos (IA)»; '
             'si existe la cuenta contable, crea el modelo estándar de Community '
             '(account.reconcile.model). El valor inicial proviene de Ajustes.',
    )
    progress = fields.Integer('Progreso', readonly=True, default=0)
    progress_msg = fields.Char('Paso actual', readonly=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('analyzing', 'Analizando'),
        ('analyzed', 'Analizado'),
        ('done', 'Finalizado'),
    ], default='draft', readonly=True)
    line_ids = fields.One2many('qif.ai.wizard.line', 'wizard_id', string='Líneas QIF')
    reconcile_proposal_ids = fields.One2many(
        'qif.ai.wizard.reconcile', 'wizard_id', string='Modelos de Conciliación',
    )
    ai_analysis_raw = fields.Text('Respuesta IA (raw)')

    total_lines = fields.Integer(compute='_compute_stats')
    new_lines = fields.Integer(compute='_compute_stats')
    duplicate_lines = fields.Integer(compute='_compute_stats')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        flds = fields_list if fields_list is not None else []
        if 'auto_promote_reconcile_ce' in flds and 'auto_promote_reconcile_ce' not in res:
            raw = (
                self.env['ir.config_parameter'].sudo().get_param('gn_qif_openai.auto_promote_reconcile', 'False') or ''
            ).strip().lower()
            res['auto_promote_reconcile_ce'] = raw in ('true', '1', 'yes')
        return res

    @api.depends('line_ids.status')
    def _compute_stats(self):
        for wiz in self:
            wiz.total_lines = len(wiz.line_ids)
            wiz.new_lines = len(wiz.line_ids.filtered(lambda l: l.status == 'new'))
            wiz.duplicate_lines = wiz.total_lines - wiz.new_lines

    def _wiz_company(self):
        return self.journal_id.company_id if self.journal_id else self.env.company

    def _reconcile_ce_bank_tag(self):
        if not self.file_format or self.file_format == 'unknown':
            snip = (
                ''.join(ch for ch in (self.file_bank_name or '') if ch.isalnum())[:4].upper()
            )
            return snip or 'BANC'
        tag_map = {
            'xlsx_atlantida': 'ATL',
            'xlsx_banpais': 'BPS',
            'xlsx_occidente_hn': 'OCC',
            'xls_ficohsa': 'FCH',
            'xls_davivienda_hn': 'DAV',
            'pdf_occident': 'OCP',
            'qif': 'QIF',
        }
        return tag_map.get(self.file_format, (self.file_format or 'BANC').replace('_', '')[:4].upper())

    def _find_equivalent_ce_reconcile_model(self, journal, match_label, match_label_param):
        Rec = self.env['account.reconcile.model']
        cid = journal.company_id.id
        param_norm = (match_label_param or '').strip().lower()
        cand = Rec.search([
            ('company_id', '=', cid),
            ('match_label', '=', match_label),
            '|',
            ('match_journal_ids', 'in', journal.ids),
            ('match_journal_ids', '=', False),
        ])
        for rec in cand:
            if (rec.match_label_param or '').strip().lower() == param_norm:
                return rec
        return Rec.browse()

    def _format_ce_reconcile_display_name(self, proposal_name):
        base = ((proposal_name or '') or _('Regla IA')).strip()[:208]
        return (_('[%s] %s') % (self._reconcile_ce_bank_tag()[:12], base))[:256]

    def _create_odoo_reconcile_models_from_proposals(self, proposals=None):
        """Crea `account.reconcile.model` en CE a partir de propuestas con cuenta válida."""
        self.ensure_one()
        journal = self.journal_id
        if not journal:
            return 0
        Learn = self.env['gn.qif.reconcile.learn']
        proposals = proposals or self.reconcile_proposal_ids.filtered(
            lambda p: p.selected and p.account_id and p.match_label_param,
        )
        created_ct = 0
        Rec = self.env['account.reconcile.model']
        for prop in proposals:
            ml = prop.match_label or 'contains'
            if ml not in ('contains', 'not_contains', 'match_regex'):
                ml = 'contains'
            equiv = self._find_equivalent_ce_reconcile_model(journal, ml, prop.match_label_param)
            if equiv:
                Learn.link_promoted_ce_model(journal, ml, prop.match_label_param, equiv)
                continue
            fingerprint = Learn.fingerprint_for(ml, prop.match_label_param)
            learn = Learn.search([
                ('journal_id', '=', journal.id),
                ('fingerprint', '=', fingerprint),
            ], limit=1)
            if learn.reconcile_model_id:
                Learn.link_promoted_ce_model(journal, ml, prop.match_label_param, learn.reconcile_model_id)
                continue
            nm = self._format_ce_reconcile_display_name(prop.name)
            existing_name = Rec.search([
                ('company_id', '=', journal.company_id.id),
                ('name', '=', nm),
            ], limit=1)
            if existing_name:
                Learn.link_promoted_ce_model(journal, ml, prop.match_label_param, existing_name)
                continue
            new_rm = Rec.create({
                'name': nm,
                'trigger': prop.trigger if prop.trigger in ('manual', 'auto_reconcile') else 'manual',
                'match_journal_ids': [Command.set([journal.id])],
                'match_label': ml,
                'match_label_param': prop.match_label_param,
                'gn_creation_source': 'ai_promoted',
                'gn_file_format_key': ((self.file_format or '')[:64]) if getattr(self, 'file_format', None) else '',
                'line_ids': [Command.create({
                    'account_id': prop.account_id.id,
                    'amount_type': 'percentage',
                    'amount_string': '100',
                })],
            })
            Learn.link_promoted_ce_model(journal, ml, prop.match_label_param, new_rm)
            created_ct += 1
        return created_ct

    @staticmethod
    def _decode(data):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data.decode('latin-1')

    def _parse_qif_raw(self, raw_bytes):
        return gn_qif_parser.parse_qif_bytes(self.journal_id, raw_bytes)

    @api.model
    def _detect_file_format(self, raw_bytes, filename=''):
        fname = (filename or '').lower()
        if fname.endswith('.pdf') or raw_bytes.startswith(b'%PDF'):
            return 'pdf_occident'
        if fname.endswith('.xlsx'):
            key = gn_qif_bank_xlsx.detect_xlsx_extract_format(raw_bytes)
            return key if key else 'unknown'
        if fname.endswith('.xls'):
            try:
                wb = xlrd.open_workbook(file_contents=raw_bytes)
                sh = wb.sheet_by_index(0)
                if _davivienda_hn_header_row(sh) is not None:
                    return 'xls_davivienda_hn'
                sname = wb.sheet_names()[0] if wb.sheet_names() else ''
                if 'AccountStatement' in sname or 'Hondur' in sname:
                    return 'xls_ficohsa'
            except Exception:
                return 'unknown'
            return 'xls_ficohsa'
        if raw_bytes.lstrip()[:6] in (b'!Type:', b'!type:'):
            return 'qif'
        if fname.endswith('.qif'):
            return 'qif'
        return 'unknown'

    @api.model
    def _parse_statement(self, raw_bytes, fmt=None, journal=None):
        fmt = fmt or 'unknown'
        jrec = journal if journal else self.env['account.journal']
        if fmt == 'pdf_occident':
            text = gn_qif_pdf_occident.extract_pdf_plain_text(raw_bytes)
            return gn_qif_pdf_occident.parse_occidente_statement_from_text(text)
        if fmt == 'xls_davivienda_hn':
            return _parse_davivienda_hn_xls(raw_bytes)
        if fmt == 'qif':
            return gn_qif_parser.parse_qif_bytes(jrec, raw_bytes)
        if fmt == 'xls_ficohsa':
            return _parse_ficohsa_xls(raw_bytes)
        if fmt in ('xlsx_atlantida', 'xlsx_banpais', 'xlsx_occidente_hn'):
            return gn_qif_bank_xlsx.parse_xlsx_by_format(raw_bytes, fmt)
        raise UserError(_('Formato de archivo no soportado: %s') % fmt)

    def _parse_qif(self):
        raw = base64.b64decode(self.qif_file)
        fmt = self.file_format if self.file_format and self.file_format != 'unknown' else self._detect_file_format(raw, self.qif_filename)
        transactions, _meta = self._parse_statement(raw, fmt=fmt, journal=self.journal_id)
        return transactions

    @api.onchange('qif_file', 'qif_filename', 'journal_id')
    def _onchange_qif_file(self):
        if not self.qif_file:
            self.file_format = 'unknown'
            return
        try:
            raw = base64.b64decode(self.qif_file)
            fmt = self._detect_file_format(raw, self.qif_filename)
            self.file_format = fmt
            transactions, meta = self._parse_statement(raw, fmt=fmt, journal=self.journal_id)
        except Exception:
            self.file_format = 'unknown'
            return

        self.date_from = meta['min_date']
        self.date_to = meta['max_date']
        self.qif_line_count = meta['count']
        self.qif_balance_end = meta.get('balance_end') or meta['total_amount']
        self.qif_balance_start = meta.get('balance_start', 0.0)

        if fmt == 'xls_ficohsa':
            self.file_bank_name = meta.get('bank_name', '')
            self.file_account_name = meta.get('account_number', '')
            self.file_currency_code = meta.get('currency', '')
            self.file_company_hint = meta.get('titular', '')
            self.file_meta_source = 'heuristic'
            self.file_meta_confidence = 0.95
            self.file_meta_evidence = _('Datos extraídos del encabezado del archivo XLS FICOHSA')
        elif fmt == 'pdf_occident':
            self.file_bank_name = meta.get('bank_name', '')
            self.file_account_name = meta.get('account_number', '')
            self.file_currency_code = meta.get('currency', '')
            self.file_company_hint = meta.get('titular', '')
            self.file_meta_source = 'heuristic'
            self.file_meta_confidence = 0.88
            self.file_meta_evidence = _('Texto extraído del PDF (layout tipo Estado de cuenta Occidente)')
        elif fmt == 'xlsx_atlantida':
            self.file_bank_name = meta.get('bank_name', '')
            self.file_account_name = meta.get('account_number', '')
            self.file_currency_code = meta.get('currency', '')
            self.file_company_hint = meta.get('titular', '')
            self.file_meta_source = 'heuristic'
            self.file_meta_confidence = 0.93
            self.file_meta_evidence = _('Encabezado Excel Banco Atlántida — columnas Débitos/Créditos')
        elif fmt == 'xlsx_banpais':
            self.file_bank_name = meta.get('bank_name', '')
            self.file_account_name = meta.get('account_number', '')
            self.file_currency_code = meta.get('currency', '')
            self.file_company_hint = meta.get('titular', '')
            self.file_meta_source = 'heuristic'
            self.file_meta_confidence = 0.93
            self.file_meta_evidence = _('Encabezado Excel Banpaís (FECHA, TRX, DÉBITO, CRÉDITO)')
        elif fmt == 'xlsx_occidente_hn':
            self.file_bank_name = meta.get('bank_name', '')
            self.file_account_name = meta.get('account_number', '')
            self.file_currency_code = meta.get('currency', '')
            self.file_company_hint = meta.get('titular', '')
            self.file_meta_source = 'heuristic'
            self.file_meta_confidence = 0.91
            self.file_meta_evidence = _('Plantilla dispersa Occidente HN en Excel (.xlsx)')
        elif fmt == 'qif':
            text = self._decode(raw)
            heur = _extract_heuristic_qif_metadata(text)
            self.file_bank_name = heur['bank']
            self.file_account_name = heur['account']
            self.file_currency_code = heur['currency']
            self.file_meta_source = 'heuristic' if any(heur.values()) else 'none'
        else:
            self.file_meta_source = 'none'

    @staticmethod
    def _hash_tx(tx):
        """Hash estable por línea. Incluye sequence para evitar colisiones cuando el banco
        repite fecha, importe y descripción en la misma fecha (requisito UNIQUE de Odoo en
        account.bank.statement.line.unique_import_id).
        """
        ref = (tx.get('payment_ref') or '').strip().upper()
        check = tx.get('ref') or ''
        seq = tx.get('sequence')
        if seq is None:
            seq = tx.get('index', 0)
        raw = f"{tx.get('date', '')}|{tx.get('amount', 0)}|{ref}|{check}|{seq}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @api.model
    def _detect_hash_duplicates(self, transactions, journal=None):
        jr = journal
        if jr is None and getattr(self, 'ids', ()) and getattr(self, 'journal_id', None):
            jr = self.journal_id
        BSL = self.env['account.bank.statement.line']
        if not jr:
            for tx in transactions:
                uid = self._hash_tx(tx)
                tx['unique_import_id'] = uid
                tx['_hash_dup'] = False
                tx['_odoo_line_id'] = False
            return transactions

        acct = jr.bank_account_id
        prefix = (sanitize_account_number(acct.acc_number) + '-' if acct else '') + str(jr.id) + '-'

        for tx in transactions:
            uid = self._hash_tx(tx)
            tx['unique_import_id'] = uid
            full_uid = prefix + uid
            existing = BSL.sudo().search([('unique_import_id', '=', full_uid)], limit=1)
            tx['_hash_dup'] = bool(existing)
            tx['_odoo_line_id'] = existing.id if existing else False
        return transactions

    def _find_matching_journal_from_hints(self, account_hint, bank_hint=''):
        self.ensure_one()
        account_hint = (account_hint or '').strip()
        bank_hint = (bank_hint or '').strip().lower()
        company = self.env.company
        journals = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', company.id),
            ('bank_account_id', '!=', False),
        ])
        if account_hint:
            hint_s = sanitize_account_number(account_hint)
            for j in journals:
                acc = j.bank_account_id.acc_number or ''
                if hint_s and sanitize_account_number(acc) == hint_s:
                    return j
            digits = ''.join(c for c in account_hint if c.isdigit())
            if len(digits) >= 4:
                last4 = digits[-4:]
                for j in journals:
                    acc = (j.bank_account_id.acc_number or '').replace(' ', '')
                    if last4 and last4 in acc:
                        return j
        if bank_hint:
            for j in journals:
                bname = (j.bank_id.name or '').lower()
                if bname and bank_hint in bname:
                    return j
        return self.env['account.journal']

    def _merge_file_metadata(self, heur, ai_meta):
        ai_meta = ai_meta or {}
        bank_ai = (ai_meta.get('bank_name') or '').strip()
        acc_ai = (ai_meta.get('account_number_or_mask') or '').strip()
        cur_ai = (ai_meta.get('currency_iso') or '').strip().upper()
        comp_ai = (ai_meta.get('company_hint') or '').strip()
        conf = float(ai_meta.get('confidence') or 0.0)
        evidence = (ai_meta.get('evidence') or '').strip()[:2000]

        bank = bank_ai or heur['bank']
        account = acc_ai or heur['account']
        currency = cur_ai or heur['currency']
        if not currency and self.env.company.currency_id:
            currency = self.env.company.currency_id.name

        has_h = bool(heur['bank'] or heur['account'] or heur['currency'])
        has_ai = bool(bank_ai or acc_ai or cur_ai or comp_ai)
        if has_h and has_ai:
            source = 'hybrid'
        elif has_ai:
            source = 'ai'
        elif has_h:
            source = 'heuristic'
        else:
            source = 'none'

        return {
            'file_bank_name': bank[:256],
            'file_account_name': account[:256],
            'file_currency_code': currency[:16] if currency else '',
            'file_company_hint': comp_ai[:256],
            'file_meta_confidence': conf if has_ai else (0.3 if has_h else 0.0),
            'file_meta_source': source,
            'file_meta_evidence': evidence,
        }

    def _call_openai_metadata(self, raw_bytes, transactions):
        excerpt = self._decode(raw_bytes)[:8000]
        sample = [
            {
                'date': str(t.get('date', '')),
                'label': (t.get('payment_ref') or '')[:220],
                'amount': t.get('amount', 0),
            }
            for t in transactions[:40]
        ]
        payload = {
            'extracto_qif': excerpt,
            'muestra_movimientos': sample,
        }
        prompt = (
            'Eres un extractor de datos bancarios. A partir del extracto QIF y la muestra de '
            'movimientos, infiere: nombre del banco o institución, número o máscara de cuenta, '
            'moneda ISO 4217 si hay evidencia, nombre de empresa o titular si aparece. '
            'Si no hay evidencia suficiente, deja cadenas vacías y confidence bajo.\n\n'
            + json.dumps(payload, ensure_ascii=False)
            + '\n\nResponde SOLO con JSON válido:\n'
            '{"bank_name":"","account_number_or_mask":"","currency_iso":"","company_hint":"",'
            '"confidence":0.0,"evidence":""}'
        )
        resp = self._openai_chat_json(
            [{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            temperature=0.05,
        )
        return json.loads(resp.choices[0].message.content)

    def _odoo_lines_in_range(self, transactions, journal=None):
        journal = journal or self.journal_id
        dates = [tx['date'] for tx in transactions if tx.get('date')]
        if not dates or not journal:
            return self.env['account.bank.statement.line']
        domain = [
            ('journal_id', '=', journal.id),
            ('date', '>=', self.date_from or min(dates)),
            ('date', '<=', self.date_to or max(dates)),
        ]
        return self.env['account.bank.statement.line'].search(domain, order='date, id')

    def _get_openai_client(self):
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('gn_qif_openai.api_key', '')
        if not api_key:
            raise UserError(_(
                'Configure la API Key de OpenAI en Ajustes > Contabilidad > QIF OpenAI.'
            ))
        return OpenAI(api_key=api_key)

    def _get_openai_model(self):
        ICP = self.env['ir.config_parameter'].sudo()
        raw = (ICP.get_param('gn_qif_openai.model', DEFAULT_OPENAI_MODEL) or '').strip()
        if not raw:
            return DEFAULT_OPENAI_MODEL
        # La API de chat usa identificadores en minúsculas (p. ej. gpt-4o, gpt-4.1-mini).
        return raw.lower()

    def _user_error_for_openai_model(self, err, model_used):
        """Error de modelo inexistente o sin acceso (HTTP 404 en chat completions)."""
        return UserError(
            _(
                'El modelo de OpenAI «%s» no existe o su clave no tiene acceso. '
                'En Ajustes → Contabilidad, bloque «QIF OpenAI», ponga un modelo válido '
                'para la API (por ejemplo: gpt-4.1-mini, gpt-4o o gpt-4.1). '
                'Compruebe en la documentación de modelos de OpenAI el id exacto para su cuenta.'
            )
            % (model_used,)
        )

    def _openai_chat_json(self, messages, **kwargs):
        """Una petición chat.completions con manejo de error homogéneo."""
        self.ensure_one()
        client = self._get_openai_client()
        model = self._get_openai_model()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
            return resp
        except NotFoundError as err:
            raise self._user_error_for_openai_model(err, model) from err
        except APIStatusError as err:
            if getattr(err, 'status_code', None) == 404:
                raise self._user_error_for_openai_model(err, model) from err
            logger.warning('OpenAI API error (model=%s): %s', model, err)
            raise UserError(_('Error al consultar OpenAI: %s') % err) from err
        except Exception as err:
            logger.exception('OpenAI request failed (model=%s)', model)
            raise UserError(_('Error al consultar OpenAI: %s') % err) from err

    def _knowledge_text_for_prompt(self):
        if not self.journal_id:
            return ''
        k = self.env['gn.qif.journal.knowledge'].search([
            ('journal_id', '=', self.journal_id.id),
        ], limit=1)
        if not k or not k.user_notes:
            return ''
        plain = html2plaintext(k.user_notes or '')
        return plain[:5000]

    def _bank_layout_hints_for_prompt(self):
        """Fragmentos configurados por banco/formato (`gn.qif.bank.statement.layout`)."""
        self.ensure_one()
        fm = self.file_format
        if not fm or fm == 'unknown':
            return ''
        Layout = self.env['gn.qif.bank.statement.layout'].sudo()
        recs = Layout.search([
            ('active', '=', True),
            ('file_format_key', '=', fm),
        ], order='sequence, id')
        texts = [(r.ai_context or '').strip() for r in recs if (r.ai_context or '').strip()]
        if not texts:
            return ''
        body = '\n\n'.join(texts[:12])
        return ('\n## Layout registrado por banco (prioridad alta)\n' + body)[:9000]

    def _reconcile_models_json_for_prompt(self):
        company = self._wiz_company()
        domain = [('company_id', '=', company.id)]
        if self.journal_id:
            domain = [
                '&',
                ('company_id', '=', company.id),
                '|',
                ('match_journal_ids', '=', False),
                ('match_journal_ids', 'in', self.journal_id.ids),
            ]
        models = self.env['account.reconcile.model'].search(domain, limit=45, order='sequence')
        out = []
        for m in models:
            jcodes = ', '.join(m.match_journal_ids.mapped('code')) or '*'
            lines_info = []
            for line in m.line_ids[:3]:
                lines_info.append({
                    'account_code': line.account_id.code if line.account_id else '',
                    'account_name': line.account_id.name if line.account_id else '',
                })
            out.append({
                'name': m.name,
                'trigger': m.trigger,
                'match_label': m.match_label,
                'match_label_param': m.match_label_param or '',
                'journals': jcodes,
                'counterpart_lines': lines_info,
            })
        return json.dumps(out, ensure_ascii=False)

    def _build_ai_prompt(self, transactions, odoo_lines):
        qif_data = [
            {
                'i': i, 'date': str(tx.get('date', '')),
                'amount': tx.get('amount', 0),
                'label': tx.get('payment_ref', ''),
                'ref': tx.get('ref', ''),
                'hash_dup': tx.get('_hash_dup', False),
            }
            for i, tx in enumerate(transactions)
        ]
        odoo_data = [
            {
                'id': ln.id, 'date': str(ln.date),
                'amount': ln.amount, 'label': ln.payment_ref or '',
                'ref': ln.ref or '',
            }
            for ln in odoo_lines
        ]
        company = self._wiz_company()
        accounts = self.env['account.account'].with_company(company).search(
            [], order='code', limit=250,
        )
        acct_data = [{'code': a.code, 'name': a.name} for a in accounts]

        file_ctx = {
            'banco_detectado_archivo': self.file_bank_name or '',
            'cuenta_detectada_archivo': self.file_account_name or '',
            'moneda_detectada': self.file_currency_code or '',
            'pista_empresa': self.file_company_hint or '',
        }
        knowledge = self._knowledge_text_for_prompt()
        layout_hints = self._bank_layout_hints_for_prompt()
        rm_json = self._reconcile_models_json_for_prompt()

        extra = ''
        if knowledge:
            extra += (
                '\n## Instrucciones y conocimiento del equipo (prioridad alta)\n'
                + knowledge + '\n'
            )
        if layout_hints:
            extra += layout_hints + '\n'
        extra += (
            '\n## Modelos de conciliación ya configurados en Odoo\n'
            + rm_json + '\n'
            'No propongas modelos redundantes si ya existen reglas equivalentes.\n'
        )
        extra += (
            '\n## Contexto detectado en el extracto (archivo)\n'
            + json.dumps(file_ctx, ensure_ascii=False) + '\n'
        )

        return (
            'Eres un asistente contable experto. Analiza transacciones bancarias QIF '
            'y compáralas con líneas ya registradas en Odoo.\n\n'
            + extra
            + '## Líneas QIF\n' + json.dumps(qif_data, ensure_ascii=False) + '\n\n'
            + '## Líneas en Odoo (mismo diario y rango)\n' + json.dumps(odoo_data, ensure_ascii=False) + '\n\n'
            + '## Catálogo de cuentas contables\n' + json.dumps(acct_data, ensure_ascii=False) + '\n\n'
            + '## Instrucciones\n'
            + '1. **Duplicados**: Para cada línea QIF con hash_dup=false, indica si hay una línea '
            'Odoo equivalente (mismo importe, fecha ±3 días, etiqueta similar). '
            'Solo marca si confidence > 0.8.\n'
            + '2. **Modelos de conciliación**: Agrupa transacciones QIF por patrón de etiqueta '
            '(comisiones, intereses, pagos recurrentes) y sugiere modelos de conciliación. '
            'Indica: nombre, tipo de coincidencia (contains, not_contains o match_regex), parámetro, '
            'código de cuenta de contrapartida del catálogo, y trigger (manual o auto_reconcile).\n'
            + 'Respeta el conocimiento del equipo y los modelos ya existentes.\n\n'
            + '## Formato de respuesta (JSON)\n'
            '{"duplicates": [{"qif_index": 0, "odoo_line_id": 1, "confidence": 0.95, '
            '"reason": "..."}], "reconcile_models": [{"name": "...", "match_label": '
            '"contains", "match_label_param": "...", "account_code": "...", '
            '"trigger": "manual"}]}\n\n'
            + 'Responde SOLO con JSON válido.'
        )

    def _call_openai(self, transactions, odoo_lines):
        prompt = self._build_ai_prompt(transactions, odoo_lines)
        resp = self._openai_chat_json(
            [{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content)

    def _apply_ai_result_to_wizard(self, transactions, ai_result):
        """Aplica la respuesta de OpenAI al asistente (líneas, propuestas, historial)."""
        self.ensure_one()
        ai_result = ai_result or {}
        ai_dups = {d['qif_index']: d for d in ai_result.get('duplicates', [])}
        line_vals = []
        for i, tx in enumerate(transactions):
            ai = ai_dups.get(i, {})
            if tx.get('_hash_dup'):
                status, odoo_id, conf = 'duplicate_hash', tx.get('_odoo_line_id'), 100.0
            elif ai.get('confidence', 0) > 0.8:
                status, odoo_id, conf = 'duplicate_ai', ai.get('odoo_line_id'), ai['confidence'] * 100
            else:
                status, odoo_id, conf = 'new', False, ai.get('confidence', 0) * 100

            line_vals.append(Command.create({
                'sequence': tx.get('sequence', i + 1),
                'date': tx.get('date'),
                'amount': tx.get('amount', 0),
                'payment_ref': tx.get('payment_ref', ''),
                'ref': tx.get('ref', ''),
                'unique_import_id': tx.get('unique_import_id', ''),
                'status': status,
                'odoo_line_id': odoo_id,
                'confidence': conf,
                'ai_reason': ai.get('reason', ''),
                'to_import': status == 'new',
            }))

        reconcile_vals = []
        company = self._wiz_company()
        for rm in ai_result.get('reconcile_models', []):
            account = self.env['account.account'].with_company(company).search(
                [('code', '=', rm.get('account_code', ''))], limit=1,
            )
            ml_ai = (rm.get('match_label') or 'contains').strip().lower()
            if ml_ai not in ('contains', 'not_contains', 'match_regex'):
                ml_ai = 'contains'
            trig = rm.get('trigger') or 'manual'
            if trig not in ('manual', 'auto_reconcile'):
                trig = 'manual'
            reconcile_vals.append(Command.create({
                'name': rm.get('name', ''),
                'match_label': ml_ai,
                'match_label_param': rm.get('match_label_param', ''),
                'account_code': rm.get('account_code', ''),
                'account_id': account.id if account else False,
                'trigger': trig,
                'selected': True,
            }))

        dup_n = len(ai_result.get('duplicates') or [])
        rm_n = len(ai_result.get('reconcile_models') or [])
        brief = (
            _('Duplicados (IA): %(d)d; modelos sugeridos: %(m)d')
            % {'d': dup_n, 'm': rm_n}
        )

        self.write({
            'state': 'analyzed',
            'line_ids': [Command.clear()] + line_vals,
            'reconcile_proposal_ids': [Command.clear()] + reconcile_vals,
            'ai_analysis_raw': json.dumps(ai_result, ensure_ascii=False, indent=2),
            'ai_summary_brief': brief,
        })

        ln_new = ln_dup = 0
        ce_created = 0
        if self.journal_id:
            ln_new, ln_dup = self.env['gn.qif.reconcile.learn'].ingest_from_ai(self, ai_result)
            brief += _(' · Aprend.: %(n)d nuevos · %(r)d refuerzos') % {'n': ln_new, 'r': ln_dup}
            if self.auto_promote_reconcile_ce:
                ce_created = self._create_odoo_reconcile_models_from_proposals()
                if ce_created:
                    brief += _(' · Modelos CE creados (ahora): %(c)d') % {'c': ce_created}

        self.write({'ai_summary_brief': brief})
        self._create_suggestion_record(ai_result)

    def _create_suggestion_record(self, ai_result):
        dup_n = len(ai_result.get('duplicates') or [])
        rm_n = len(ai_result.get('reconcile_models') or [])
        summary = _(
            'Duplicados sugeridos por IA: %(d)d; modelos de conciliación propuestos: %(m)d',
        ) % {'d': dup_n, 'm': rm_n}
        self.env['gn.qif.suggestion'].sudo().create({
            'company_id': self.env.company.id,
            'journal_id': self.journal_id.id if self.journal_id else False,
            'summary': summary,
            'detail': json.dumps(ai_result, ensure_ascii=False, indent=2)[:65000],
            'qif_filename': self.qif_filename or '',
            'state': 'new',
        })

    def action_match_journal(self):
        self.ensure_one()
        j = self._find_matching_journal_from_hints(
            self.file_account_name, self.file_bank_name,
        )
        if not j:
            raise UserError(_('No se encontró un diario bancario que coincida con la cuenta o banco detectados.'))
        self.journal_id = j
        return self._reopen()

    def _notify_progress(self, pct, msg):
        self.write({'progress': pct, 'progress_msg': msg})
        bus_payload = {
            'progress': int(pct),
            'message': msg,
            'done': pct >= 100,
        }
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'gn_qif_progress',
            bus_payload,
        )
        self.env.cr.commit()

    def action_analyze(self):
        self.ensure_one()
        self.write({'state': 'analyzing', 'progress': 0, 'progress_msg': _('Iniciando…')})
        self.env.cr.commit()
        batch = self.env['gn.qif.ai.batch'].create({
            'wizard_id': self.id,
            'file_datas': self.qif_file,
            'qif_filename': self.qif_filename or '',
            'journal_id': self.journal_id.id if self.journal_id else False,
            'allow_reimport': self.allow_reimport,
            'phase': 'parse',
            'state': 'draft',
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'qif_ai_import_progress',
            'name': _('Analizando con IA'),
            'params': {'batch_id': batch.id},
        }

    def _run_analysis_pipeline(self):
        """Pipeline síncrono (p. ej. shell). El flujo normal usa `gn.qif.ai.batch` + acción cliente."""
        self._notify_progress(10, _('Paso 1/5 — Leyendo estado de cuenta…'))
        raw = base64.b64decode(self.qif_file)
        fmt = self._detect_file_format(raw, self.qif_filename)
        self.file_format = fmt
        transactions, meta = self._parse_statement(raw, fmt=fmt, journal=self.journal_id)
        if not transactions:
            raise UserError(_('No se encontraron transacciones en el archivo.'))

        if fmt == 'xls_ficohsa':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.95,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado XLS FICOHSA'),
            }
        elif fmt == 'pdf_occident':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.88,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Pie de página PDF — layout Estado de cuenta (Occidente HN)'),
            }
        elif fmt == 'xls_davivienda_hn':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.92,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado XLS Davivienda Honduras'),
            }
        elif fmt == 'xlsx_atlantida':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.93,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado Excel Banco Atlántida (.xlsx)'),
            }
        elif fmt == 'xlsx_banpais':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.93,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado Excel Banpaís (.xlsx)'),
            }
        elif fmt == 'xlsx_occidente_hn':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.91,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Plantilla dispersa Occidente HN en Excel (.xlsx)'),
            }
        else:
            text = self._decode(raw)
            heur = _extract_heuristic_qif_metadata(text)
            self._notify_progress(25, _('Paso 2/5 — Detectando banco y cuenta con IA…'))
            ai_meta = {}
            try:
                ai_meta = self._call_openai_metadata(raw, transactions)
            except Exception as e:
                logger.warning('OpenAI metadata: %s', e)
            merged = self._merge_file_metadata(heur, ai_meta)

        self.write({
            'date_from': meta['min_date'],
            'date_to': meta['max_date'],
            'qif_line_count': meta['count'],
            'qif_balance_end': meta.get('balance_end') or meta['total_amount'],
            'qif_balance_start': meta.get('balance_start', 0.0),
            **merged,
        })
        self.env.cr.commit()

        self._notify_progress(45, _('Paso 3/5 — Emparejando diario y detectando duplicados…'))
        journal = self.journal_id
        if not journal:
            journal = self._find_matching_journal_from_hints(
                merged['file_account_name'], merged['file_bank_name'],
            )
            if journal:
                self.journal_id = journal
        journal = self.journal_id
        transactions = self._detect_hash_duplicates(transactions, journal)
        odoo_lines = self._odoo_lines_in_range(transactions, journal)

        self._notify_progress(60, _('Paso 4/5 — Analizando con OpenAI (puede tardar)…'))
        ai_result = self._call_openai(transactions, odoo_lines)

        self._notify_progress(85, _('Paso 5/5 — Procesando resultados…'))
        self._notify_progress(100, _('Análisis completado'))
        self._apply_ai_result_to_wizard(transactions, ai_result)

    def action_create_reconcile_models(self):
        self.ensure_one()
        if not self.journal_id:
            raise UserError(_('Seleccione un diario bancario de destino para crear los modelos.'))
        created = self._create_odoo_reconcile_models_from_proposals()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Modelos de Conciliación'),
                'message': _('%d modelo(s) creado(s).') % created,
                'sticky': False,
                'type': 'success',
                'next': self._reopen(),
            },
        }

    def action_import_lines(self):
        self.ensure_one()
        if not self.journal_id:
            raise UserError(_('Seleccione un diario bancario de destino para importar las líneas.'))
        to_import = self.line_ids.filtered('to_import')
        if not to_import:
            raise UserError(_('No hay líneas marcadas para importar.'))

        journal = self.journal_id
        History = self.env['gn.qif.import.history']
        file_hash = History.hash_from_datas(self.qif_file)
        existing_history = History.search([
            ('company_id', '=', journal.company_id.id),
            ('journal_id', '=', journal.id),
            ('file_hash', '=', file_hash),
        ], limit=1)
        if existing_history and not self.allow_reimport:
            raise UserError(_(
                'Este archivo QIF ya fue importado en este diario. '
                'Active "Permitir reimportar este archivo" o elimine '
                'el registro en Contabilidad → Historial importaciones QIF.'
            ))
        transactions = []
        total = 0.0
        for ln in to_import.sorted('sequence'):
            tx = {
                'date': ln.date,
                'amount': ln.amount,
                'payment_ref': ln.payment_ref,
                'unique_import_id': ln.unique_import_id,
                'sequence': ln.sequence,
                'journal_id': journal.id,
            }
            if ln.ref:
                tx['ref'] = ln.ref
            total += ln.amount
            transactions.append(tx)

        attachment = self.env['ir.attachment'].create({
            'name': self.qif_filename or 'qif_ai_import.qif',
            'datas': self.qif_file,
            'res_model': 'account.bank.statement',
        })
        acct_number = journal.bank_account_id.acc_number if journal.bank_account_id else None
        stmt_vals = [{
            'reference': self.qif_filename or _('Importación QIF IA'),
            'balance_end_real': total,
            'transactions': transactions,
            'attachment_ids': [Command.set(attachment.ids)],
        }]
        stmt_vals = journal._complete_bank_statement_vals(stmt_vals, journal, acct_number, attachment)
        statement_ids, ignored = journal._create_bank_statements(stmt_vals, raise_no_imported_file=False)

        if existing_history:
            existing_history.sudo().unlink()
        History.create({
            'company_id': journal.company_id.id,
            'journal_id': journal.id,
            'filename': self.qif_filename or '',
            'file_hash': file_hash,
            'line_count': len(to_import),
            'lines_imported': len(to_import) - ignored,
            'lines_skipped': ignored,
            'statement_ids': [Command.set(statement_ids)],
            'attachment_id': attachment.id,
        })

        self.state = 'done'
        imported = len(to_import) - ignored
        if statement_ids:
            return self._action_qif_open_imported_statements(statement_ids, journal, imported, ignored)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Importación QIF'),
                'message': _('Todas las líneas ya estaban importadas (%d ignoradas).') % ignored,
                'sticky': False, 'type': 'warning',
            },
        }

    @api.model
    def gn_bulk_import_statement(self, journal, raw_bytes, filename='', allow_reimport=False):
        """Crea un extracto Odoo desde un archivo (sin revisión manual del asistente).

        Solo se envían líneas que aún no existen por `unique_import_id` previo del mismo archivo.
        """
        journal = journal[:1]
        if not journal:
            raise UserError(_('Seleccione un diario bancario de destino para importar.'))
        fname = filename or _('extracto_bancario')
        datas_b64 = base64.b64encode(raw_bytes)
        fmt = self._detect_file_format(raw_bytes, fname)
        if fmt == 'unknown':
            raise UserError(_(
                'Formato no reconocido («%(fn)s»). Soporte actual: Excel .xlsx (Atlántida, Banpaís, Occidente HN), '
                'XLS (FICOHSA, Davivienda HN), PDF Occidente, QIF.',
                fn=fname,
            ))

        txs, _meta = self._parse_statement(raw_bytes, fmt=fmt, journal=journal)
        if not txs:
            raise UserError(_('No se encontraron transacciones en «%s».') % fname)

        txs = self._detect_hash_duplicates(txs, journal)
        hash_dup_n = sum(1 for t in txs if t.get('_hash_dup'))
        to_lines = [t for t in txs if not t.get('_hash_dup')]

        History = self.env['gn.qif.import.history']
        file_hash = History.hash_from_datas(datas_b64)
        existing_history = History.search([
            ('company_id', '=', journal.company_id.id),
            ('journal_id', '=', journal.id),
            ('file_hash', '=', file_hash),
        ], limit=1)
        if existing_history and not allow_reimport:
            raise UserError(_(
                'El archivo ya consta como importado en este diario. '
                'Active «permitir reimportar» o elimine la entrada del historial de importaciones.'
            ))

        transactions = []
        total = 0.0
        for ln in sorted(to_lines, key=lambda x: x.get('sequence', 0)):
            tx = {
                'date': ln['date'],
                'amount': ln['amount'],
                'payment_ref': ln.get('payment_ref', ''),
                'unique_import_id': ln['unique_import_id'],
                'sequence': ln.get('sequence', 0),
                'journal_id': journal.id,
            }
            if ln.get('ref'):
                tx['ref'] = ln['ref']
            total += ln['amount']
            transactions.append(tx)

        if not transactions:
            return {
                'statement_ids': [],
                'filename': fname,
                'imported_lines': 0,
                'ignored_duplicate_hash': hash_dup_n,
                'skipped_create_duplicates': 0,
                'file_format': fmt,
            }

        attachment = self.env['ir.attachment'].create({
            'name': fname,
            'datas': datas_b64,
            'res_model': 'account.bank.statement',
        })
        acct_number = journal.bank_account_id.acc_number if journal.bank_account_id else None
        stmt_vals = [{
            'reference': fname or _('Importación extracto IA'),
            'balance_end_real': total,
            'transactions': transactions,
            'attachment_ids': [Command.set(attachment.ids)],
        }]
        stmt_vals = journal._complete_bank_statement_vals(stmt_vals, journal, acct_number, attachment)
        statement_ids, ignored = journal._create_bank_statements(stmt_vals, raise_no_imported_file=False)
        imported = len(transactions) - ignored

        if existing_history:
            existing_history.sudo().unlink()
        History.create({
            'company_id': journal.company_id.id,
            'journal_id': journal.id,
            'filename': fname,
            'file_hash': file_hash,
            'line_count': len(transactions),
            'lines_imported': imported,
            'lines_skipped': ignored,
            'statement_ids': [Command.set(statement_ids)],
            'attachment_id': attachment.id,
        })

        return {
            'statement_ids': statement_ids,
            'filename': fname,
            'imported_lines': imported,
            'ignored_duplicate_hash': hash_dup_n,
            'skipped_create_duplicates': ignored,
            'file_format': fmt,
        }

    def _action_qif_open_imported_statements(self, statement_ids, journal, imported, ignored):
        """Tras importar: paridad con Enterprise = líneas de extracto (conciliación) o listado CE vía OCA + OWL."""
        self.ensure_one()
        sids = list(statement_ids or [])
        msg = _(
            'Importación «%(file)s»: %(n)d línea(s) creada(s), %(i)d movimiento(s) duplicado(s) omitido(s).',
        ) % {
            'file': self.qif_filename or 'QIF',
            'n': imported,
            'i': ignored,
        }
        if hasattr(
            self.env['account.bank.statement.line'],
            '_action_open_bank_reconciliation_widget',
        ):
            return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
                extra_domain=[('statement_id', 'in', sids)] if sids else [],
                default_context={
                    'default_journal_id': journal.id,
                    'search_default_journal_id': journal.id,
                    'search_default_not_matched': True,
                    'gn_qif_import_message': msg,
                    'gn_qif_reco_tools_enabled': True,
                },
                name=_('Conciliación: %s') % (self.qif_filename or 'QIF'),
                kanban_first=True,
            )
        # Community: listado de líneas (account_statement_base) + cabecera OWL gn_qif_bank_st_line
        try:
            result = dict(self.env['ir.actions.act_window']._for_xml_id(
                'account_statement_base.account_bank_statement_line_action',
            ))
        except Exception:  # noqa: BLE001 — xml_id faltante (p. ej. módulo OCA desinstalado)
            return self._action_qif_open_imported_statements_fallback_statements(
                sids, journal, msg,
            )
        base_dom = result.get('domain', []) or []
        if not isinstance(base_dom, (list, tuple)):
            base_dom = []
        st_dom = [('statement_id', 'in', sids)] if sids else [('id', '=', False)]
        result['domain'] = list(base_dom) + st_dom
        ctx = {}
        c = result.get('context', {})
        if isinstance(c, dict):
            ctx = dict(c)
        elif isinstance(c, str) and c.strip():
            from ast import literal_eval
            try:
                ctx = literal_eval(c)
            except (ValueError, SyntaxError, TypeError):
                ctx = {}
        ctx.update({
            'default_journal_id': journal.id,
            'search_default_journal_id': journal.id,
            'search_default_not_reconciled': True,
            'gn_qif_import_message': msg,
            'gn_qif_reco_tools_enabled': True,
        })
        result['name'] = _('Líneas de extracto: %s') % (self.qif_filename or 'QIF')
        result['context'] = ctx
        result['view_mode'] = 'list,form'
        result['views'] = [
            (self.env.ref('gn_qif_openai_reconcile.view_gn_qif_bank_st_line_list').id, 'list'),
            (self.env.ref('account_statement_base.account_bank_statement_line_form').id, 'form'),
        ]
        search = self.env.ref('account_statement_base.account_bank_statement_line_search', raise_if_not_found=False)
        if search:
            result['search_view_id'] = [search.id, 'search']
        return result

    def _action_qif_open_imported_statements_fallback_statements(self, statement_ids, journal, message):
        """Si no hay account_statement_base: abrir extraets bancarios (solo account)."""
        self.ensure_one()
        xmlid = 'account.action_bank_statement_tree'
        if journal.type == 'cash':
            xmlid = 'account.action_view_bank_statement_tree'
        elif journal.type == 'credit':
            xmlid = 'account.action_credit_statement_tree'
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        result = dict(action)
        base_dom = result.get('domain', []) or []
        if not isinstance(base_dom, (list, tuple)):
            base_dom = []
        result['domain'] = list(base_dom) + [('id', 'in', list(statement_ids or []))]
        ctx = {}
        c = result.get('context', {})
        if isinstance(c, dict):
            ctx = dict(c)
        elif isinstance(c, str) and c.strip():
            from ast import literal_eval
            try:
                ctx = literal_eval(c)
            except (ValueError, SyntaxError, TypeError):
                ctx = {}
        ctx['default_journal_id'] = journal.id
        if journal.id:
            ctx['search_default_journal_id'] = journal.id
        result['name'] = _('Extractos: %s') % (self.qif_filename or 'QIF')
        result['context'] = ctx
        return result

    def action_apply_all(self):
        self.action_create_reconcile_models()
        return self.action_import_lines()

    def _reopen(self):
        # Incluir `views`: si la acción va en JSON (p. ej. desde process_next → doAction en OWL),
        # no pasa por clean_action() del servidor y el web client requiere `views` (no solo view_mode).
        return {
            'type': 'ir.actions.act_window',
            'name': _('Análisis QIF con IA'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }


class QifAiWizardLine(models.TransientModel):
    _name = 'qif.ai.wizard.line'
    _description = 'Línea de análisis QIF'
    _order = 'sequence'

    wizard_id = fields.Many2one('qif.ai.wizard', ondelete='cascade', required=True)
    sequence = fields.Integer()
    date = fields.Date('Fecha')
    amount = fields.Float('Monto', digits=(16, 2))
    payment_ref = fields.Char('Etiqueta')
    ref = fields.Char('Referencia')
    unique_import_id = fields.Char('Hash')
    status = fields.Selection([
        ('new', 'Nueva'),
        ('duplicate_hash', 'Duplicada (hash)'),
        ('duplicate_ai', 'Duplicada (IA)'),
    ], default='new', string='Estado')
    odoo_line_id = fields.Many2one('account.bank.statement.line', string='Línea Odoo')
    confidence = fields.Float('Confianza %')
    ai_reason = fields.Char('Razón IA')
    to_import = fields.Boolean('Importar', default=True)


class QifAiWizardReconcile(models.TransientModel):
    _name = 'qif.ai.wizard.reconcile'
    _description = 'Propuesta de modelo de conciliación'

    wizard_id = fields.Many2one('qif.ai.wizard', ondelete='cascade', required=True)
    name = fields.Char('Nombre', required=True)
    match_label = fields.Selection([
        ('contains', 'Contiene'),
        ('not_contains', 'No contiene'),
        ('match_regex', 'Regex'),
    ], default='contains', string='Coincidencia')
    match_label_param = fields.Char('Parámetro')
    account_code = fields.Char('Código Cuenta')
    account_id = fields.Many2one('account.account', string='Cuenta Contable')
    trigger = fields.Selection([
        ('manual', 'Manual'),
        ('auto_reconcile', 'Automático'),
    ], default='manual', string='Tipo')
    selected = fields.Boolean('Crear', default=True)
