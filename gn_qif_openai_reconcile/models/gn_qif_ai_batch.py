# -*- coding: utf-8 -*-
import base64
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)

PHASE_ORDER = ['parse', 'metadata_ai', 'merge', 'dupes', 'openai', 'finalize']
TOTAL_STEPS = len(PHASE_ORDER)
# Fases locales (sin llamadas OpenAI pesadas): se ejecutan en un solo RPC.
FAST_PHASES = frozenset({'parse', 'metadata_ai', 'merge', 'dupes'})


def _txs_to_json(transactions):
    out = []
    for tx in transactions:
        d = dict(tx)
        if d.get('date') is not None:
            d['date'] = d['date'].isoformat() if hasattr(d['date'], 'isoformat') else str(d['date'])
        out.append(d)
    return json.dumps(out, ensure_ascii=False)


def _txs_from_json(text):
    if not text:
        return []
    data = json.loads(text)
    from datetime import date as date_cls
    import datetime as dt_mod
    for d in data:
        if d.get('date') and isinstance(d['date'], str):
            try:
                d['date'] = date_cls.fromisoformat(d['date'][:10])
            except ValueError:
                d['date'] = dt_mod.datetime.strptime(d['date'][:10], '%Y-%m-%d').date()
    return data


def _transactions_from_dict(batch, work_cache):
    """Lista de movimientos: caché de la petición (misma invocación a process_next) o JSON guardado."""
    if work_cache is not None and work_cache.get('tx_work') is not None:
        return work_cache['tx_work']
    return _txs_from_json(batch.transactions_json)


class GnQifAiBatch(models.TransientModel):
    _name = 'gn.qif.ai.batch'
    _description = 'Lote de análisis IA (estados de cuenta QIF/XLS)'

    name = fields.Char(default='Análisis IA', readonly=True)
    wizard_id = fields.Many2one(
        'qif.ai.wizard', string='Asistente', required=True, ondelete='cascade',
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('processing', 'Procesando'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], default='draft', readonly=True)
    phase = fields.Selection([
        ('parse', 'Lectura'),
        ('metadata_ai', 'Metadatos IA'),
        ('merge', 'Fusión'),
        ('dupes', 'Duplicados'),
        ('openai', 'Análisis IA'),
        ('finalize', 'Finalizar'),
    ], default='parse', readonly=True)
    error_message = fields.Text(string='Error', readonly=True)

    file_datas = fields.Binary(string='Archivo', required=True)
    qif_filename = fields.Char(string='Nombre archivo')
    journal_id = fields.Many2one('account.journal', string='Diario')
    allow_reimport = fields.Boolean()
    file_format = fields.Selection([
        ('qif', 'QIF'),
        ('xls_ficohsa', 'XLS (FICOHSA)'),
        ('xls_davivienda_hn', 'XLS (Davivienda HN)'),
        ('pdf_occident', 'PDF (extracto Honduras / Occidente)'),
        ('xlsx_atlantida', 'Excel (.xlsx) Banco Atlántida'),
        ('xlsx_banpais', 'Excel (.xlsx) Banpaís'),
        ('xlsx_occidente_hn', 'Excel (.xlsx) Banco Occidente HN'),
        ('unknown', 'Desconocido'),
    ], readonly=True)

    transactions_json = fields.Text(string='Transacciones (JSON)')
    meta_json = fields.Text(string='Meta parseo')
    ai_meta_json = fields.Text(string='Meta IA (QIF)')
    ai_result_json = fields.Text(string='Resultado IA principal')

    progress = fields.Float(
        string='Progreso %',
        compute='_compute_progress',
    )

    @api.depends('phase', 'state')
    def _compute_progress(self):
        for rec in self:
            if rec.state == 'done':
                rec.progress = 100.0
            elif rec.state == 'error':
                rec.progress = 0.0
            else:
                try:
                    idx = PHASE_ORDER.index(rec.phase or 'parse')
                except ValueError:
                    idx = 0
                rec.progress = min(100.0, ((idx + 1) / float(TOTAL_STEPS)) * 100.0)

    def process_next(self):
        """Ejecuta el pipeline en 3 RPCs: (1) fases rápidas, (2) OpenAI, (3) finalizar."""
        self.ensure_one()
        wiz = self.wizard_id
        if not wiz:
            raise UserError(_('Asistente no encontrado.'))
        if self.state == 'done':
            return self._get_progress_data()
        if self.state == 'error':
            return self._get_progress_data()

        if self.state == 'draft':
            self.state = 'processing'

        # Odoo 19: BaseModel usa __slots__; no se pueden asignar self._raw_cache / self._tx_work.
        work_cache = {'raw': None, 'tx_work': None}

        last_result = None
        try:
            # Bloque 1: lectura, metadatos IA (QIF), fusión, duplicados — un solo round-trip HTTP.
            if self.phase in FAST_PHASES:
                step_messages = []
                while self.phase in FAST_PHASES:
                    last_result = self._dispatch_phase(wiz, work_cache)
                    if last_result and last_result.get('message'):
                        step_messages.append(last_result['message'])
                if last_result and len(step_messages) > 1:
                    last_result = {
                        **last_result,
                        'message': _('Preparación: %s') % ' · '.join(step_messages),
                    }
                return self._get_progress_data(last_result=last_result)

            # Bloque 2: análisis principal OpenAI (lento; su propio RPC).
            if self.phase == 'openai':
                last_result = self._step_openai(wiz)
                self.phase = 'finalize'
                return self._get_progress_data(last_result=last_result)

            # Bloque 3: escribir resultados en el wizard.
            if self.phase == 'finalize':
                last_result = self._step_finalize(wiz)
                self.write({'state': 'done'})
                return self._get_progress_data(last_result=last_result)

        except Exception as e:
            logger.exception('gn.qif.ai.batch process_next')
            self.write({'state': 'error', 'error_message': str(e)})
            if wiz:
                wiz.write({'state': 'draft', 'progress': 0, 'progress_msg': ''})
            return self._get_progress_data(last_result={'state': 'error', 'message': str(e)})

        return self._get_progress_data(last_result=last_result)

    def _dispatch_phase(self, wiz, work_cache):
        """Un paso de fase rápida y avance de `phase`."""
        if self.phase == 'parse':
            res = self._step_parse(wiz, work_cache)
            self.phase = 'metadata_ai' if self.file_format == 'qif' else 'merge'
            return res
        if self.phase == 'metadata_ai':
            res = self._step_metadata_ai(wiz, work_cache)
            self.phase = 'merge'
            return res
        if self.phase == 'merge':
            res = self._step_merge(wiz, work_cache)
            self.phase = 'dupes'
            return res
        if self.phase == 'dupes':
            res = self._step_dupes(wiz, work_cache)
            self.phase = 'openai'
            return res
        raise AssertionError('Fase inesperada en _dispatch_phase: %s' % self.phase)

    def get_progress_data(self):
        """RPC público para el cliente OWL (progreso y acción al terminar)."""
        self.ensure_one()
        return self._get_progress_data()

    def _get_progress_data(self, last_result=None):
        self.ensure_one()
        progress = self.progress
        if self.state == 'done':
            progress = 100.0
        data = {
            'state': self.state,
            'progress': progress,
            'batch_name': self.name or _('Análisis IA'),
            'phase': self.phase,
            'last_result': last_result,
            'wizard_id': self.wizard_id.id if self.wizard_id else False,
            'error_message': self.error_message or '',
            'processed': PHASE_ORDER.index(self.phase) + 1 if self.phase in PHASE_ORDER else 0,
            'total': TOTAL_STEPS,
            'ok': 1 if self.state == 'done' else 0,
            'errors': 1 if self.state == 'error' else 0,
        }
        if self.state == 'done' and self.wizard_id:
            data['wizard_action'] = self.wizard_id._reopen()
        return data

    def _step_parse(self, wiz, work_cache):
        raw = base64.b64decode(self.file_datas)
        work_cache['raw'] = raw
        fmt = wiz._detect_file_format(raw, self.qif_filename)
        jrec = self.journal_id
        transactions, meta = wiz._parse_statement(raw, fmt=fmt, journal=jrec)
        if not transactions:
            raise UserError(_('No se encontraron transacciones en el archivo.'))
        work_cache['tx_work'] = transactions
        self.write({
            'file_format': fmt,
            'transactions_json': _txs_to_json(transactions),
            'meta_json': json.dumps(meta, default=str),
        })
        wiz.write({
            'qif_file': self.file_datas,
            'qif_filename': self.qif_filename,
            'file_format': fmt,
            'journal_id': self.journal_id.id if self.journal_id else False,
            'allow_reimport': self.allow_reimport,
            'date_from': meta['min_date'],
            'date_to': meta['max_date'],
            'qif_line_count': meta['count'],
            'qif_balance_end': meta.get('balance_end') or meta['total_amount'],
            'qif_balance_start': meta.get('balance_start', 0.0),
            'state': 'analyzing',
        })
        if fmt == 'xls_ficohsa':
            wiz.write({
                'file_bank_name': meta.get('bank_name', ''),
                'file_account_name': meta.get('account_number', ''),
                'file_currency_code': meta.get('currency', ''),
                'file_company_hint': meta.get('titular', ''),
                'file_meta_confidence': 0.95,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado XLS FICOHSA'),
            })
        elif fmt == 'xls_davivienda_hn':
            wiz.write({
                'file_bank_name': meta.get('bank_name', ''),
                'file_account_name': meta.get('account_number', ''),
                'file_currency_code': meta.get('currency', ''),
                'file_company_hint': meta.get('titular', ''),
                'file_meta_confidence': 0.92,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado XLS Davivienda Honduras'),
            })
        elif fmt == 'pdf_occident':
            wiz.write({
                'file_bank_name': meta.get('bank_name', ''),
                'file_account_name': meta.get('account_number', ''),
                'file_currency_code': meta.get('currency', ''),
                'file_company_hint': meta.get('titular', ''),
                'file_meta_confidence': 0.88,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Texto PDF (layout Estado de cuenta Occidente HN)'),
            })
        elif fmt == 'xlsx_atlantida':
            wiz.write({
                'file_bank_name': meta.get('bank_name', ''),
                'file_account_name': meta.get('account_number', ''),
                'file_currency_code': meta.get('currency', ''),
                'file_company_hint': meta.get('titular', ''),
                'file_meta_confidence': 0.93,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado Excel Banco Atlántida (.xlsx)'),
            })
        elif fmt == 'xlsx_banpais':
            wiz.write({
                'file_bank_name': meta.get('bank_name', ''),
                'file_account_name': meta.get('account_number', ''),
                'file_currency_code': meta.get('currency', ''),
                'file_company_hint': meta.get('titular', ''),
                'file_meta_confidence': 0.93,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado Excel Banpaís (.xlsx)'),
            })
        elif fmt == 'xlsx_occidente_hn':
            wiz.write({
                'file_bank_name': meta.get('bank_name', ''),
                'file_account_name': meta.get('account_number', ''),
                'file_currency_code': meta.get('currency', ''),
                'file_company_hint': meta.get('titular', ''),
                'file_meta_confidence': 0.91,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Plantilla dispersa Occidente HN en Excel (.xlsx)'),
            })
        return {
            'filename': self.qif_filename or 'archivo',
            'state': 'done',
            'message': _('Archivo leído: %s movimientos') % len(transactions),
        }

    def _step_metadata_ai(self, wiz, work_cache):
        raw = work_cache.get('raw') or base64.b64decode(self.file_datas)
        transactions = _transactions_from_dict(self, work_cache)
        ai_meta = {}
        try:
            ai_meta = wiz._call_openai_metadata(raw, transactions)
        except UserError:
            raise
        except Exception as e:
            logger.warning('OpenAI metadata: %s', e)
        self.ai_meta_json = json.dumps(ai_meta, ensure_ascii=False)
        return {
            'filename': self.qif_filename or 'QIF',
            'state': 'done',
            'message': _('Metadatos IA obtenidos'),
        }

    def _step_merge(self, wiz, work_cache):
        from odoo.addons.gn_qif_openai_reconcile.wizard import qif_ai_wizard as wiz_mod
        meta = json.loads(self.meta_json) if self.meta_json else {}
        if self.file_format == 'xls_ficohsa':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.95,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado XLS FICOHSA'),
            }
        elif self.file_format == 'pdf_occident':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.88,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Pie de página PDF — layout Estado de cuenta (Occidente HN)'),
            }
        elif self.file_format == 'xls_davivienda_hn':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.92,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado XLS Davivienda Honduras'),
            }
        elif self.file_format == 'xlsx_atlantida':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.93,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado Excel Banco Atlántida (.xlsx)'),
            }
        elif self.file_format == 'xlsx_banpais':
            merged = {
                'file_bank_name': meta.get('bank_name', '')[:256],
                'file_account_name': meta.get('account_number', '')[:256],
                'file_currency_code': meta.get('currency', '')[:16],
                'file_company_hint': meta.get('titular', '')[:256],
                'file_meta_confidence': 0.93,
                'file_meta_source': 'heuristic',
                'file_meta_evidence': _('Encabezado Excel Banpaís (.xlsx)'),
            }
        elif self.file_format == 'xlsx_occidente_hn':
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
            raw = work_cache.get('raw') or base64.b64decode(self.file_datas)
            text = wiz._decode(raw)
            heur = wiz_mod._extract_heuristic_qif_metadata(text)
            ai_meta = json.loads(self.ai_meta_json) if self.ai_meta_json else {}
            merged = wiz._merge_file_metadata(heur, ai_meta)
        wiz.write(merged)
        return {'state': 'done', 'message': _('Datos del extracto unificados')}

    def _step_dupes(self, wiz, work_cache):
        transactions = _transactions_from_dict(self, work_cache)
        journal = wiz.journal_id
        if not journal:
            journal = wiz._find_matching_journal_from_hints(
                wiz.file_account_name, wiz.file_bank_name,
            )
            if journal:
                wiz.journal_id = journal
        journal = wiz.journal_id
        transactions = wiz._detect_hash_duplicates(transactions, journal)
        work_cache['tx_work'] = transactions
        self.transactions_json = _txs_to_json(transactions)
        return {'state': 'done', 'message': _('Duplicados evaluados')}

    def _step_openai(self, wiz):
        transactions = _transactions_from_dict(self, None)
        journal = wiz.journal_id
        odoo_lines = wiz._odoo_lines_in_range(transactions, journal)
        ai_result = wiz._call_openai(transactions, odoo_lines)
        self.ai_result_json = json.dumps(ai_result, ensure_ascii=False)
        self.transactions_json = _txs_to_json(transactions)
        return {'state': 'done', 'message': _('Análisis IA completado')}

    def _step_finalize(self, wiz):
        transactions = _txs_from_json(self.transactions_json)
        ai_result = json.loads(self.ai_result_json) if self.ai_result_json else {}
        wiz._apply_ai_result_to_wizard(transactions, ai_result)
        return {'state': 'done', 'message': _('Resultados aplicados al asistente')}
