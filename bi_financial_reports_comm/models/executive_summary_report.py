# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.tools import format_amount
from odoo.tools.date_utils import get_month, get_fiscal_year, get_quarter
from dateutil.relativedelta import relativedelta


class ExecutiveSummaryReport(models.Model):
    _name = 'executive.summary.report'
    _description = 'Executive Summary Report'

    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    journal_ids = fields.Many2many('account.journal', string='Journal')

    def _get_account_by_type(self, account_types):
        return self.env['account.account'].search([('account_type', 'in', account_types)])

    def _get_balance(self, account_ids, date_from, date_to, date_scope='strict'):
        """Sum balance of given accounts. date_scope: 'strict' (range) or 'from_beginning' (to date_to)."""
        target_move = self.env.context.get('target_move', 'all')
        domain = [('account_id', 'in', account_ids.ids)]
        if target_move == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        if date_scope == 'strict':
            if date_from:
                domain.append(('date', '>=', date_from))
            if date_to:
                domain.append(('date', '<=', date_to))
        else:
            if date_to:
                domain.append(('date', '<=', date_to))
        if self.env.context.get('journal_ids'):
            domain.append(('journal_id', 'in', self.env.context['journal_ids']))
        res = self.env['account.move.line']._read_group(
            domain, groupby=['account_id'], aggregates=['balance:sum', 'debit:sum', 'credit:sum']
        )
        total_balance = sum(r[1] for r in res)
        total_debit = sum(r[2] for r in res)
        total_credit = sum(r[3] for r in res)
        return total_balance, total_debit, total_credit

    def _get_cash_amounts(self, date_from, date_to):
        """Cash received (debits), cash spent (credits), closing balance."""
        cash_accounts = self._get_account_by_type(['asset_cash', 'liability_credit_card'])
        if not cash_accounts:
            return 0.0, 0.0, 0.0
        _, cash_received, cash_spent = self._get_balance(cash_accounts, date_from, date_to, 'strict')
        closing_balance, _, _ = self._get_balance(cash_accounts, None, date_to, 'from_beginning')
        return cash_received, cash_spent, closing_balance

    def _get_comparison_period_dates(self, date_from, date_to, comparison_filter, number_period, date_filter_type):
        if comparison_filter in ("no_comparison", None):
            return None
        date_from = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
        date_to = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
        if comparison_filter == "previous_period":
            pt = date_filter_type or "month"
            if pt == "month":
                cmp_to = date_to - relativedelta(months=number_period)
                cmp_from, cmp_to = get_month(cmp_to)
            elif pt == "quarter":
                cmp_to = date_to - relativedelta(months=3 * number_period)
                cmp_from, cmp_to = get_quarter(cmp_to)
            else:
                cmp_to = date_to - relativedelta(years=number_period)
                cmp_from, cmp_to = get_fiscal_year(cmp_to)
            return {"date_from": cmp_from, "date_to": cmp_to, "string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y")}
        if comparison_filter == "same_last_year":
            cmp_from = date_from - relativedelta(years=number_period)
            cmp_to = date_to - relativedelta(years=number_period)
            return {"date_from": cmp_from, "date_to": cmp_to, "string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y")}
        if comparison_filter == "specific_date":
            cmp_date_to = self.env.context.get("comparison_date_to")
            if cmp_date_to:
                cmp_to = fields.Date.from_string(cmp_date_to)
                pt = date_filter_type or "month"
                if pt == "month":
                    cmp_from, cmp_to = get_month(cmp_to)
                elif pt == "quarter":
                    cmp_from, cmp_to = get_quarter(cmp_to)
                else:
                    cmp_from, cmp_to = get_fiscal_year(cmp_to)
                return {"date_from": cmp_from, "date_to": cmp_to, "string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y")}
        return None

    def _format_val(self, val, currency):
        curr = currency or self.env.company.currency_id
        return format_amount(self.env, val if val is not None else 0.0, curr)

    @api.model
    def get_data_executive_summary(self):
        context = self.env.context
        existing = self.search([], limit=1, order="id DESC")
        date_from = context.get("date_from") or existing.date_from
        date_to = context.get("date_to") or existing.date_to
        journal_ids = context.get("journal_ids") or (existing.journal_ids.ids if existing.journal_ids else [])
        if not date_from or not date_to:
            fiscal = get_fiscal_year(fields.Date.today())
            date_from = fiscal[0]
            date_to = fields.Date.today()

        currency = self.env.company.currency_id
        ctx = dict(context, journal_ids=journal_ids)

        def fmt(v):
            return format_amount(self.env, v, currency) if v is not None else "0.00"

        # Cash section
        cash_received, cash_spent, closing_bank = self.with_context(ctx)._get_cash_amounts(date_from, date_to)
        cash_surplus = cash_received - cash_spent

        # Profitability (P&L)
        income_acc = self._get_account_by_type(['income', 'income_other'])
        exp_direct = self._get_account_by_type(['expense_direct_cost'])
        exp_other = self._get_account_by_type(['expense', 'expense_depreciation'])
        rev_bal, _, _ = self.with_context(ctx)._get_balance(income_acc, date_from, date_to, 'strict')
        cost_bal, _, _ = self.with_context(ctx)._get_balance(exp_direct, date_from, date_to, 'strict')
        exp_bal, _, _ = self.with_context(ctx)._get_balance(exp_other, date_from, date_to, 'strict')
        income_total = -rev_bal if income_acc else 0.0
        cost_revenue = cost_bal if exp_direct else 0.0
        expenses = exp_bal if exp_other else 0.0
        gross_profit = income_total - cost_revenue
        net_profit = gross_profit - expenses

        # Balance Sheet (as of date_to)
        recv_acc = self._get_account_by_type(['asset_receivable'])
        pay_acc = self._get_account_by_type(['liability_payable'])
        asset_acc = self._get_account_by_type([
            'asset_cash', 'asset_receivable', 'asset_current', 'asset_prepayments',
            'asset_fixed', 'asset_non_current'
        ])
        liab_acc = self._get_account_by_type([
            'liability_payable', 'liability_credit_card', 'liability_current',
            'liability_non_current', 'equity', 'equity_unaffected'
        ])
        receivable_bal, _, _ = self.with_context(ctx)._get_balance(recv_acc, None, date_to, 'from_beginning')
        payable_bal, _, _ = self.with_context(ctx)._get_balance(pay_acc, None, date_to, 'from_beginning')
        total_assets, _, _ = self.with_context(ctx)._get_balance(asset_acc, None, date_to, 'from_beginning')
        total_liab, _, _ = self.with_context(ctx)._get_balance(liab_acc, None, date_to, 'from_beginning')
        net_assets = total_assets + total_liab

        # Performance ratios
        gross_margin_pct = (gross_profit / income_total * 100) if income_total else 0.0
        net_margin_pct = (net_profit / income_total * 100) if income_total else 0.0
        roi_pct = (net_profit / total_assets * 100) if total_assets else 0.0

        # Draft warning
        target_move = context.get('target_move', 'all')
        has_draft_warning = False
        if target_move == 'posted':
            draft_domain = [
                ('display_type', '=', False), ('parent_state', '=', 'draft'),
                ('date', '>=', date_from), ('date', '<=', date_to),
            ]
            if journal_ids:
                draft_domain.append(('journal_id', 'in', journal_ids))
            has_draft_warning = bool(self.env['account.move.line'].search(draft_domain, limit=1))

        rows = [
            {'section': 'cash', 'label': 'cash_received', 'key': 'cash_received', 'value': cash_received, 'formatted': fmt(cash_received)},
            {'section': 'cash', 'label': 'cash_spent', 'key': 'cash_spent', 'value': -cash_spent, 'formatted': fmt(-cash_spent), 'negative_red': True},
            {'section': 'cash', 'label': 'cash_surplus', 'key': 'cash_surplus', 'value': cash_surplus, 'formatted': fmt(cash_surplus)},
            {'section': 'cash', 'label': 'closing_bank', 'key': 'closing_bank', 'value': closing_bank, 'formatted': fmt(closing_bank)},
            {'section': 'profitability', 'label': 'income', 'key': 'income', 'value': income_total, 'formatted': fmt(income_total)},
            {'section': 'profitability', 'label': 'cost_revenue', 'key': 'cost_revenue', 'value': cost_revenue, 'formatted': fmt(cost_revenue), 'negative_red': True},
            {'section': 'profitability', 'label': 'gross_profit', 'key': 'gross_profit', 'value': gross_profit, 'formatted': fmt(gross_profit)},
            {'section': 'profitability', 'label': 'expenses', 'key': 'expenses', 'value': expenses, 'formatted': fmt(expenses), 'negative_red': True},
            {'section': 'profitability', 'label': 'net_profit', 'key': 'net_profit', 'value': net_profit, 'formatted': fmt(net_profit)},
            {'section': 'balancesheet', 'label': 'receivables', 'key': 'receivables', 'value': receivable_bal, 'formatted': fmt(receivable_bal)},
            {'section': 'balancesheet', 'label': 'payables', 'key': 'payables', 'value': -payable_bal, 'formatted': fmt(-payable_bal), 'negative_red': True},
            {'section': 'balancesheet', 'label': 'net_assets', 'key': 'net_assets', 'value': net_assets, 'formatted': fmt(net_assets)},
            {'section': 'performance', 'label': 'gross_margin', 'key': 'gross_margin', 'value': gross_margin_pct, 'formatted': f"{gross_margin_pct:.1f}%", 'is_pct': True},
            {'section': 'performance', 'label': 'net_margin', 'key': 'net_margin', 'value': net_margin_pct, 'formatted': f"{net_margin_pct:.1f}%", 'is_pct': True},
            {'section': 'performance', 'label': 'roi', 'key': 'roi', 'value': roi_pct, 'formatted': f"{roi_pct:.1f}%", 'is_pct': True},
        ]

        comparison = None
        comparison_filter = context.get("comparison_filter", "no_comparison")
        cmp_period = self._get_comparison_period_dates(
            date_from, date_to,
            comparison_filter,
            context.get("comparison_number_period", 1) or 1,
            context.get("date_filter_type", "month"),
        )
        if cmp_period:
            cf, cs, cb = self.with_context(ctx)._get_cash_amounts(
                cmp_period["date_from"], cmp_period["date_to"])
            r2, _, _ = self.with_context(ctx)._get_balance(income_acc, cmp_period["date_from"], cmp_period["date_to"], 'strict')
            c2, _, _ = self.with_context(ctx)._get_balance(exp_direct, cmp_period["date_from"], cmp_period["date_to"], 'strict')
            e2, _, _ = self.with_context(ctx)._get_balance(exp_other, cmp_period["date_from"], cmp_period["date_to"], 'strict')
            inc2 = -r2 if income_acc else 0.0
            gp2 = inc2 - (c2 if exp_direct else 0.0)
            np2 = gp2 - (e2 if exp_other else 0.0)
            rec2, _, _ = self.with_context(ctx)._get_balance(recv_acc, None, cmp_period["date_to"], 'from_beginning')
            pay2, _, _ = self.with_context(ctx)._get_balance(pay_acc, None, cmp_period["date_to"], 'from_beginning')
            ta2, _, _ = self.with_context(ctx)._get_balance(asset_acc, None, cmp_period["date_to"], 'from_beginning')
            comparison = {
                'string': cmp_period['string'],
                'rows': [
                    {'key': 'cash_received', 'value': cf, 'formatted': fmt(cf)},
                    {'key': 'cash_spent', 'value': -cs, 'formatted': fmt(-cs)},
                    {'key': 'cash_surplus', 'value': cf - cs, 'formatted': fmt(cf - cs)},
                    {'key': 'closing_bank', 'value': cb, 'formatted': fmt(cb)},
                    {'key': 'income', 'value': inc2, 'formatted': fmt(inc2)},
                    {'key': 'cost_revenue', 'value': c2 if exp_direct else 0, 'formatted': fmt(c2 if exp_direct else 0)},
                    {'key': 'gross_profit', 'value': gp2, 'formatted': fmt(gp2)},
                    {'key': 'expenses', 'value': e2 if exp_other else 0, 'formatted': fmt(e2 if exp_other else 0)},
                    {'key': 'net_profit', 'value': np2, 'formatted': fmt(np2)},
                    {'key': 'receivables', 'value': rec2, 'formatted': fmt(rec2)},
                    {'key': 'payables', 'value': -pay2, 'formatted': fmt(-pay2)},
                    {'key': 'net_assets', 'value': ta2 + total_liab, 'formatted': fmt(ta2 + total_liab)},
                    {'key': 'gross_margin', 'value': (gp2 / inc2 * 100) if inc2 else 0, 'formatted': f"{(gp2 / inc2 * 100) if inc2 else 0:.1f}%"},
                    {'key': 'net_margin', 'value': (np2 / inc2 * 100) if inc2 else 0, 'formatted': f"{(np2 / inc2 * 100) if inc2 else 0:.1f}%"},
                    {'key': 'roi', 'value': (np2 / ta2 * 100) if ta2 else 0, 'formatted': f"{(np2 / ta2 * 100) if ta2 else 0:.1f}%"},
                ],
            }
            comp_map = {r['key']: r for r in comparison['rows']}
            for row in rows:
                row['comparison_value'] = comp_map.get(row['key'], {}).get('value')
                row['comparison_formatted'] = comp_map.get(row['key'], {}).get('formatted', '')

        currency_data = {'symbol': currency.symbol, 'position': currency.position, 'decimal_places': currency.decimal_places}

        period_label = f"{date_from}" + (" - " + str(date_to) if date_from != date_to else "")
        if context.get('date_filter_type') == 'year':
            period_label = str(date_to.year) if date_to else ""

        result = {
            'rows': rows,
            'currency_data': currency_data,
            'period_label': period_label,
            'date_from': date_from,
            'date_to': date_to,
            'comparison': comparison,
            'has_draft_warning': has_draft_warning,
        }
        report_cur = context.get('report_currency_id')
        if report_cur:
            self.env['bi.report.currency.helper'].apply_executive_summary(result, report_cur)
        return result

    @api.model
    def executive_summary_excel_report(self, data):
        import xlwt
        from io import BytesIO
        import base64

        rows = data.get("rows", [])
        period_label = data.get("period_label", "")

        workbook = xlwt.Workbook(encoding="UTF-8")
        sheet = workbook.add_sheet("Resumen ejecutivo")

        title_style = xlwt.easyxf(
            "font: bold True, name Arial, height 280; "
            "align: vertical center, horizontal center; "
            "pattern: pattern solid, fore_colour gray25;"
        )
        header_style = xlwt.easyxf(
            "font: bold True, name Arial, height 220; "
            "align: vertical center; "
            "pattern: pattern solid, fore_colour gray25;"
        )
        section_style = xlwt.easyxf(
            "font: bold True, name Arial, height 200; "
            "align: vertical center; "
            "pattern: pattern solid, fore_colour gray25;"
        )
        row_style = xlwt.easyxf("font: name Arial, height 180; align: vertical center;")

        section_labels = {
            "cash": "Efectivo",
            "profitability": "Rentabilidad",
            "balancesheet": "Balance general",
            "performance": "Rendimiento",
        }
        row_labels = {
            "cash_received": "Efectivo recibido",
            "cash_spent": "Efectivo gastado",
            "cash_surplus": "Superávit de efectivo",
            "closing_bank": "Balance bancario de cierre",
            "income": "Ingreso",
            "cost_revenue": "Costo de ingresos",
            "gross_profit": "Ganancia bruta",
            "expenses": "Gastos",
            "net_profit": "Ganancias netas",
            "receivables": "Por cobrar",
            "payables": "Por pagar",
            "net_assets": "Activos netos",
            "gross_margin": "Margen de ganancia bruta",
            "net_margin": "Margen neto de ganancias",
            "roi": "Retorno de la inversión",
        }

        sheet.write_merge(0, 1, 0, 1, "Resumen ejecutivo", title_style)
        sheet.write(2, 0, period_label, header_style)
        sheet.col(0).width = 12000
        sheet.col(1).width = 5000

        excel_row = 4
        last_section = None
        for row in rows:
            if row.get("section") and row["section"] != last_section:
                last_section = row["section"]
                sheet.write(excel_row, 0, section_labels.get(row["section"], row["section"]), section_style)
                excel_row += 1
            if row.get("label"):
                sheet.write(excel_row, 0, row_labels.get(row["label"], row["label"]), row_style)
                sheet.write(excel_row, 1, row.get("formatted", "0.00"), row_style)
                excel_row += 1

        buf = BytesIO()
        workbook.save(buf)
        buf.seek(0)
        excel_b64 = base64.b64encode(buf.read()).decode("utf-8")
        return {"excel_file": excel_b64, "file_name": "Resumen_ejecutivo.xls"}
