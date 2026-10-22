# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

"""Reporte Fiscal / Declaración Fiscal.

Equivalente comunitario simplificado del *Generic Tax Report* del
módulo Enterprise ``account_reports``. Calcula, por impuesto y tipo
(venta / compra):

* **Base** — suma del balance de las líneas base ligadas al impuesto
  (vía ``account_move_line_account_tax_rel``).
* **Impuesto** — suma del balance de las líneas de impuesto
  (``account_move_line.tax_line_id``).

Para presentación se muestra siempre como cantidad positiva: ventas
(crédito) se niegan, compras (débito) se conservan.

El método ``get_data_tax_report`` devuelve la misma estructura para
ambos menús (Reporte fiscal y Declaración fiscal); la diferencia es
puramente visual (manejada en el front).

Soporta comparativas (período anterior, mismo período del año
pasado y fecha específica) devolviendo varias *columnas* en
``columns`` y, por impuesto, los importes por columna.
"""

import base64
import io
import re

import xlsxwriter
from babel.dates import format_date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools.date_utils import get_month, get_quarter, get_fiscal_year


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value):
    """Convierte HTML simple (campo ``description`` de account.tax) en
    texto plano para mostrar como etiqueta corta en el reporte.
    """
    if not value:
        return ""
    text = _HTML_TAG_RE.sub(" ", str(value))
    return " ".join(text.split())


class TaxReport(models.Model):
    _name = 'tax.report'
    _description = 'Tax Report'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _normalize_amount(self, type_tax_use, balance):
        """Convierte el balance contable en monto positivo de presentación.
        Ventas se almacenan como crédito (balance negativo), por eso se
        niegan; compras como débito (balance positivo).
        """
        if type_tax_use == 'sale':
            return -balance
        return balance

    @api.model
    def _build_base_filters(self, date_from, date_to, journal_ids, target_move):
        params = [date_from, date_to]
        where = ['aml.date BETWEEN %s AND %s']
        if target_move == 'posted':
            where.append("aml.parent_state = 'posted'")
        else:
            where.append("aml.parent_state IN ('posted', 'draft')")
        if journal_ids:
            where.append('aml.journal_id IN %s')
            params.append(tuple(journal_ids))
        return where, params

    @api.model
    def _fetch_base_amounts(self, date_from, date_to, journal_ids, target_move):
        """Devuelve {tax_id: base_amount} sumando balance de líneas
        base (no de impuesto) ligadas a cada impuesto.
        """
        where, params = self._build_base_filters(date_from, date_to, journal_ids, target_move)
        where.append('aml.tax_line_id IS NULL')
        where.append("tax.type_tax_use IN ('sale', 'purchase')")
        query = """
            SELECT tax.id AS tax_id, tax.type_tax_use, SUM(aml.balance) AS amount
            FROM account_move_line aml
            JOIN account_move_line_account_tax_rel rel ON rel.account_move_line_id = aml.id
            JOIN account_tax tax ON tax.id = rel.account_tax_id
            WHERE %s
            GROUP BY tax.id, tax.type_tax_use
        """ % ' AND '.join(where)
        self.env.cr.execute(query, params)
        return {row['tax_id']: (row['type_tax_use'], row['amount'] or 0.0)
                for row in self.env.cr.dictfetchall()}

    @api.model
    def _fetch_tax_amounts(self, date_from, date_to, journal_ids, target_move):
        """Devuelve {tax_id: tax_amount} sumando balance de líneas de
        impuesto (`tax_line_id` apunta al impuesto).
        """
        where, params = self._build_base_filters(date_from, date_to, journal_ids, target_move)
        where.append("tax.type_tax_use IN ('sale', 'purchase')")
        query = """
            SELECT tax.id AS tax_id, tax.type_tax_use, SUM(aml.balance) AS amount
            FROM account_move_line aml
            JOIN account_tax tax ON tax.id = aml.tax_line_id
            WHERE %s
            GROUP BY tax.id, tax.type_tax_use
        """ % ' AND '.join(where)
        self.env.cr.execute(query, params)
        return {row['tax_id']: (row['type_tax_use'], row['amount'] or 0.0)
                for row in self.env.cr.dictfetchall()}

    # ------------------------------------------------------------------
    # Period helpers (replican la lógica de Balance Sheet/P&L)
    # ------------------------------------------------------------------
    @api.model
    def _format_period_label(self, date_from, date_to, date_filter_type):
        lang = (self.env.context.get('lang') or self.env.user.lang or 'en_US').replace('-', '_')
        try:
            if date_filter_type == 'month':
                label = format_date(date_from, format='LLLL y', locale=lang)
                return (label[:1].upper() + label[1:]) if label else label
            if date_filter_type == 'quarter':
                q = (date_from.month - 1) // 3 + 1
                return f"{date_from.year} Q{q}"
            if date_filter_type == 'year':
                return date_from.strftime('%Y')
        except Exception:
            pass
        return f"{date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}"

    @api.model
    def _get_comparison_columns(self, date_from, date_to, comparison_filter,
                                number_period, date_filter_type):
        """Devuelve la lista de períodos comparativos (sin incluir el
        período principal). Respeta el orden ascendente/descendente
        ya en el front.
        """
        if comparison_filter in (None, '', 'no_comparison'):
            return []
        number_period = number_period or 1
        cols = []
        if comparison_filter == 'previous_period':
            pt = date_filter_type or 'month'
            cur_to = date_to
            for _i in range(number_period):
                if pt == 'month':
                    cmp_to = cur_to - relativedelta(months=1)
                    cmp_from, cmp_to = get_month(cmp_to)
                elif pt == 'quarter':
                    cmp_to = cur_to - relativedelta(months=3)
                    cmp_from, cmp_to = get_quarter(cmp_to)
                else:
                    cmp_to = cur_to - relativedelta(years=1)
                    cmp_from, cmp_to = get_fiscal_year(cmp_to)
                cols.append((cmp_from, cmp_to))
                cur_to = cmp_to
        elif comparison_filter == 'same_last_year':
            for i in range(1, number_period + 1):
                cmp_from = date_from - relativedelta(years=i)
                cmp_to = date_to - relativedelta(years=i)
                cols.append((cmp_from, cmp_to))
        elif comparison_filter == 'specific_date':
            cmp_to_raw = self.env.context.get('comparison_date_to')
            if cmp_to_raw:
                cmp_to = fields.Date.from_string(cmp_to_raw) if isinstance(cmp_to_raw, str) else cmp_to_raw
                cols.append((cmp_to, cmp_to))
        return cols

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @api.model
    def get_data_tax_report(self):
        ctx = self.env.context
        date_from = ctx.get('date_from')
        date_to = ctx.get('date_to')
        journal_ids = ctx.get('journal_ids') or []
        target_move = ctx.get('target_move') or 'posted'
        date_filter_type = ctx.get('date_filter_type') or 'month'
        comparison_filter = ctx.get('comparison_filter', 'no_comparison')
        comparison_number = ctx.get('comparison_number_period', 1) or 1
        period_order = ctx.get('comparison_period_order', 'descending')

        today = fields.Date.today()
        if not date_from:
            date_from = today.replace(day=1)
        if not date_to:
            date_to = today
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        currency = self.env.company.currency_id

        # Construir lista de columnas (período principal + comparativas).
        cmp_periods = self._get_comparison_columns(
            date_from, date_to, comparison_filter, comparison_number, date_filter_type,
        )
        columns = [{
            'key': 'main',
            'label': self._format_period_label(date_from, date_to, date_filter_type),
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
        }]
        for idx, (cf, ct) in enumerate(cmp_periods):
            columns.append({
                'key': f'cmp_{idx}',
                'label': self._format_period_label(cf, ct, date_filter_type),
                'date_from': fields.Date.to_string(cf),
                'date_to': fields.Date.to_string(ct),
            })
        if period_order == 'ascending':
            columns = list(reversed(columns))

        # Ejecutar SQL una vez por columna.
        per_column_data = {}
        for col in columns:
            cf = fields.Date.from_string(col['date_from'])
            ct = fields.Date.from_string(col['date_to'])
            base_map = self._fetch_base_amounts(cf, ct, journal_ids, target_move)
            tax_map = self._fetch_tax_amounts(cf, ct, journal_ids, target_move)
            per_column_data[col['key']] = (base_map, tax_map)

        # Conjunto global de impuestos a presentar.
        all_tax_ids = set()
        for base_map, tax_map in per_column_data.values():
            all_tax_ids.update(base_map.keys())
            all_tax_ids.update(tax_map.keys())
        taxes = self.env['account.tax'].browse(all_tax_ids).sorted(
            key=lambda t: (t.type_tax_use, t.sequence, t.id)
        )

        sections = {
            'sale': {'label': _('Ventas'), 'taxes': [], 'totals': {}},
            'purchase': {'label': _('Compras'), 'taxes': [], 'totals': {}},
        }
        for sec in sections.values():
            sec['totals'] = {
                col['key']: {'base': 0.0, 'tax': 0.0} for col in columns
            }

        zero_threshold_columns = {col['key'] for col in columns}

        for tax in taxes:
            ttu = tax.type_tax_use
            if ttu not in sections:
                continue
            row_amounts = {}
            non_zero_any = False
            for col in columns:
                base_map, tax_map = per_column_data[col['key']]
                base_balance = base_map.get(tax.id, (ttu, 0.0))[1]
                tax_balance = tax_map.get(tax.id, (ttu, 0.0))[1]
                base_amount = self._normalize_amount(ttu, base_balance)
                tax_amount = self._normalize_amount(ttu, tax_balance)
                if not (currency.is_zero(base_amount) and currency.is_zero(tax_amount)):
                    non_zero_any = True
                row_amounts[col['key']] = {'base': base_amount, 'tax': tax_amount}
                sections[ttu]['totals'][col['key']]['base'] += base_amount
                sections[ttu]['totals'][col['key']]['tax'] += tax_amount
            if not non_zero_any:
                continue
            sections[ttu]['taxes'].append({
                'id': tax.id,
                'name': tax.name,
                'type_tax_use': ttu,
                'amount_label': _strip_html(tax.description),
                'amounts': row_amounts,
            })

        # Resumen tipo "Declaración fiscal" por columna.
        declaration_totals = {}
        for col in columns:
            sales_tax = sections['sale']['totals'][col['key']]['tax']
            purchase_tax = sections['purchase']['totals'][col['key']]['tax']
            declaration_totals[col['key']] = {
                'sales_tax': sales_tax,
                'purchase_tax': purchase_tax,
                'net_tax_due': sales_tax - purchase_tax,
            }

        has_draft_warning = False
        if target_move == 'posted':
            draft_domain = [
                ('parent_state', '=', 'draft'),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('tax_ids', '!=', False),
            ]
            if journal_ids:
                draft_domain.append(('journal_id', 'in', journal_ids))
            has_draft_warning = bool(
                self.env['account.move.line'].search(draft_domain, limit=1)
            )

        # Mantener compatibilidad con la primera versión: campos planos
        # del período principal.
        main_key = next((c['key'] for c in columns if c['key'] == 'main'), columns[0]['key'])
        sale_main = sections['sale']['totals'][main_key]
        purch_main = sections['purchase']['totals'][main_key]

        result = {
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
            'company': self.env.company.name,
            'currency_data': {
                'id': currency.id,
                'symbol': currency.symbol,
                'position': currency.position,
                'decimal_places': currency.decimal_places,
            },
            'columns': columns,
            'sections': sections,
            'declaration_totals': declaration_totals,
            'totals': {
                'sales_tax': sale_main['tax'],
                'sales_base': sale_main['base'],
                'purchase_tax': purch_main['tax'],
                'purchase_base': purch_main['base'],
                'net_tax_due': sale_main['tax'] - purch_main['tax'],
            },
            'has_draft_warning': has_draft_warning,
        }
        report_cur = ctx.get('report_currency_id')
        if report_cur:
            self.env['bi.report.currency.helper'].apply_tax_report(result, report_cur)
        return result

    @api.model
    def action_open_tax_aml(self, options, tax_id, kind, drill_date_from, drill_date_to):
        """Abre apuntes: kind 'base' (líneas base con impuesto) o 'tax' (líneas de impuesto)."""
        opts = dict(options or {})
        opts["drill_date_from"] = drill_date_from
        opts["drill_date_to"] = drill_date_to
        helper = self.env["bi.report.drilldown.helper"]
        tid = int(tax_id)
        if kind == "tax":
            extra = [("tax_line_id", "=", tid)]
        else:
            extra = [("tax_line_id", "=", False), ("tax_ids", "in", [tid])]
        domain = helper.aml_domain(opts, account_id=None, extra_domain=extra)
        return helper.action_aml_window(domain)

    @api.model
    def tax_report_owl_xlsx(self, data):
        """Export XLSX desde la vista OWL."""
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = wb.add_worksheet(_('Reporte fiscal'))
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        row = 0
        sheet.write(row, 0, data.get('company') or '', bold)
        row += 1
        sheet.write(row, 0, str(data.get('date_from') or ''))
        sheet.write(row, 1, str(data.get('date_to') or ''))
        row += 2
        cols = data.get('columns') or []
        sheet.write(row, 0, _('Impuesto'), bold)
        ci = 1
        for col in cols:
            sheet.write(row, ci, col.get('label') or col.get('key') or '', bold)
            ci += 1
        row += 1
        for sec_key in ('sale', 'purchase'):
            sec = (data.get('sections') or {}).get(sec_key) or {}
            sheet.write(row, 0, sec.get('label') or sec_key, bold)
            row += 1
            for tax in sec.get('taxes') or []:
                sheet.write(row, 0, tax.get('name') or '')
                ci = 1
                for col in cols:
                    ck = col.get('key')
                    cell = (tax.get('amounts') or {}).get(ck) or {}
                    tax_amt = float(cell.get('tax') or 0.0)
                    sheet.write_number(row, ci, tax_amt, money)
                    ci += 1
                row += 1
        wb.close()
        buf.seek(0)
        return {
            'excel_file': base64.b64encode(buf.read()).decode('utf-8'),
            'file_name': 'Tax_report.xlsx',
        }
