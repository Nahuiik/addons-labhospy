# -*- coding: utf-8 -*-
import calendar
from datetime import date, timedelta

from odoo import api, fields, models


class BanksWeeklyBalanceReport(models.TransientModel):
    """Asistente para informe mensual por semanas (saldos bancarios en Excel)."""

    _name = 'banks.weekly.balance.report'
    _description = 'Informe semanal de saldos bancarios (por mes)'

    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    year = fields.Integer(
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    month = fields.Selection(
        selection=[
            ('1', 'Enero'),
            ('2', 'Febrero'),
            ('3', 'Marzo'),
            ('4', 'Abril'),
            ('5', 'Mayo'),
            ('6', 'Junio'),
            ('7', 'Julio'),
            ('8', 'Agosto'),
            ('9', 'Septiembre'),
            ('10', 'Octubre'),
            ('11', 'Noviembre'),
            ('12', 'Diciembre'),
        ],
        string='Mes',
        required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    journal_ids = fields.Many2many(
        comodel_name='account.journal',
        string='Diarios de banco',
        domain=[('type', 'in', ('bank', 'cash'))],
        required=True,
    )
    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company_id = res.get('company_id') or self.env.company.id
        if isinstance(company_id, (tuple, list)):
            company_id = company_id[0]
        if (
            company_id
            and 'journal_ids' in fields_list
            and not res.get('journal_ids')
        ):
            journals = self.env['banks.weekly.balance.common'].search_balance_journals(
                company_id,
            )
            res['journal_ids'] = [(6, 0, journals.ids)]
        return res

    @api.onchange('company_id')
    def _onchange_company_journal_defaults(self):
        if self.company_id:
            self.journal_ids = self.env['banks.weekly.balance.common'].search_balance_journals(
                self.company_id.id,
            )

    def _month_week_ranges(self):
        """Bloques consecutivos de hasta 7 días dentro del mes calendario."""
        self.ensure_one()
        if self.date_from and self.date_to:
            return self._period_week_ranges(self.date_from, self.date_to)
        month = int(self.month)
        _first_dow, last_day = calendar.monthrange(int(self.year), month)
        month_start = date(int(self.year), month, 1)
        month_end = date(int(self.year), month, last_day)
        return self._period_week_ranges(month_start, month_end)

    @api.model
    def _period_week_ranges(self, period_start, period_end):
        """Bloques consecutivos de hasta 7 días en un rango arbitrario."""
        if period_start > period_end:
            period_start, period_end = period_end, period_start
        ranges = []
        week_no = 1
        cursor_date = period_start
        while cursor_date <= period_end:
            week_end = min(cursor_date + timedelta(days=6), period_end)
            ranges.append((week_no, cursor_date, week_end))
            week_no += 1
            cursor_date = week_end + timedelta(days=1)
        return period_start, period_end, ranges

    def action_export_xlsx(self):
        self.ensure_one()
        return self.env.ref(
            'gn_banks_balance.action_banks_weekly_balance_report_xlsx'
        ).report_action(self, data={'wizard_id': self.id})

    def action_export_html(self):
        self.ensure_one()
        return self.env.ref(
            'gn_banks_balance.action_banks_weekly_balance_report_html'
        ).report_action(self)
