# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from calendar import monthrange
from datetime import date

from odoo import api, fields, models, _


class L10nHnEmployeeIsrMonthly(models.Model):
    """Acumulado mensual de ingresos y créditos fiscales para ISR (HN)."""

    _name = 'l10n.hn.employee.isr.monthly'
    _description = 'Acumulado mensual ISR (HN)'
    _order = 'year desc, month desc, employee_id'

    PAYSLIP_CONFIRMED_STATES = ('done', 'paid', 'validated', 'verify')

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee', required=True, ondelete='cascade', index=True,
    )
    year = fields.Integer(required=True, index=True)
    month = fields.Integer(required=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, readonly=True)

    amount_salary = fields.Monetary(
        string='Salario gravable',
        currency_field='currency_id',
        help='Suma de líneas BASIC del mes.',
    )
    amount_commission = fields.Monetary(
        string='Comisiones gravables',
        currency_field='currency_id',
    )
    amount_gross_month = fields.Monetary(
        string='Ingresos brutos mes',
        currency_field='currency_id',
        help='Salario + comisiones del mes calendario.',
    )
    amount_ihss_month = fields.Monetary(string='IHSS mes', currency_field='currency_id')
    amount_rap_month = fields.Monetary(string='RAP mes', currency_field='currency_id')
    amount_isr_withheld_month = fields.Monetary(string='ISR retenido mes', currency_field='currency_id')

    ytd_gross = fields.Monetary(
        string='Ingresos brutos YTD',
        currency_field='currency_id',
        help='Salario + comisiones acumulados en el año hasta este mes.',
    )
    ytd_ihss = fields.Monetary(string='IHSS YTD', currency_field='currency_id')
    ytd_rap = fields.Monetary(string='RAP YTD', currency_field='currency_id')
    ytd_isr_withheld = fields.Monetary(string='ISR retenido YTD', currency_field='currency_id')

    projected_salary_annual = fields.Monetary(
        string='Salario anual proyectado',
        currency_field='currency_id',
    )
    projected_commission_ytd = fields.Monetary(
        string='Comisiones YTD (sin proyección)',
        currency_field='currency_id',
    )
    amount_medical_credit = fields.Monetary(string='Gastos médicos (crédito)', currency_field='currency_id')
    amount_other_credits = fields.Monetary(string='Otros créditos', currency_field='currency_id')
    amount_total_credits = fields.Monetary(string='Total créditos fiscales', currency_field='currency_id')
    amount_net_taxable = fields.Monetary(string='Renta neta gravable', currency_field='currency_id')
    amount_isr_annual = fields.Monetary(string='ISR anual calculado', currency_field='currency_id')
    amount_isr_target_ytd = fields.Monetary(
        string='ISR objetivo YTD',
        currency_field='currency_id',
        help='Cuota acumulada esperada según meses transcurridos.',
    )
    amount_isr_balance = fields.Monetary(
        string='Saldo ISR',
        currency_field='currency_id',
        help='Objetivo YTD menos ISR ya retenido.',
    )

    payslip_ids = fields.Many2many(
        'hr.payslip',
        'l10n_hn_emp_isr_monthly_payslip_rel',
        'isr_monthly_id', 'payslip_id',
        string='Recibos del mes',
        readonly=True,
    )

    _l10n_hn_isr_monthly_employee_period_uniq = models.Constraint(
        'unique(employee_id, year, month)',
        'Ya existe un acumulado ISR mensual para este empleado y período.',
    )

    @api.depends('employee_id', 'year', 'month')
    def _compute_name(self):
        month_names = {
            1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic',
        }
        for rec in self:
            if rec.employee_id and rec.year and rec.month:
                rec.name = '%s / %s-%02d' % (
                    rec.employee_id.name or '',
                    rec.year,
                    rec.month,
                )
            else:
                rec.name = _('Nuevo')

    @api.model
    def _find_payslips_for_month(self, employee, year, month, company=None):
        start_d = date(year, month, 1)
        end_d = date(year, month, monthrange(year, month)[1])
        domain = [
            ('employee_id', '=', employee.id),
            ('state', 'in', self.PAYSLIP_CONFIRMED_STATES),
            ('credit_note', '=', False),
            ('date_from', '<=', end_d),
            ('date_to', '>=', start_d),
        ]
        if company:
            domain.append(('company_id', '=', company.id))
        return self.env['hr.payslip'].search(domain)

    @api.model
    def _line_sum(self, payslips, code):
        if not payslips:
            return 0.0
        rows = self.env['hr.payslip.line']._read_group(
            [('slip_id', 'in', payslips.ids), ('code', '=', code)],
            [],
            ['total:sum'],
        )
        return float(rows[0][0] or 0.0) if rows else 0.0

    @api.model
    def _commission_total(self, payslips):
        rules = self.env['hr.salary.rule'].search([('l10n_hn_counts_as_commission', '=', True)])
        codes = set(rules.mapped('code')) or {'COMISIONES'}
        if not payslips:
            return 0.0
        rows = self.env['hr.payslip.line']._read_group(
            [('slip_id', 'in', payslips.ids), ('code', 'in', list(codes))],
            [],
            ['total:sum'],
        )
        return float(rows[0][0] or 0.0) if rows else 0.0

    @api.model
    def regenerate_month(self, employee, year, month, company=None):
        """Consolida ingresos/créditos del mes y proyección ISR anual."""
        company = company or employee.company_id
        if not company:
            return self.env[self._name]

        payslips = self._find_payslips_for_month(employee, year, month, company=company)
        existing = self.search([
            ('employee_id', '=', employee.id),
            ('year', '=', year),
            ('month', '=', month),
        ], limit=1)

        if not payslips:
            if existing:
                existing.unlink()
            return self.env[self._name]

        amount_salary = self._line_sum(payslips, 'BASIC')
        amount_commission = self._commission_total(payslips)
        amount_gross_month = amount_salary + amount_commission
        amount_ihss_month = abs(self._line_sum(payslips, 'IHSS_EMP'))
        amount_rap_month = abs(self._line_sum(payslips, 'RAP_FOVIIF_EMP'))
        amount_isr_withheld_month = abs(self._line_sum(payslips, 'ISR'))

        as_of = date(year, month, monthrange(year, month)[1])
        IsrConfig = self.env['l10n.hn.isr.config'].search([
            ('year', '=', year),
            ('company_id', '=', company.id),
            ('state', '=', 'validated'),
            ('active', '=', True),
        ], limit=1)

        snapshot = {}
        if IsrConfig and getattr(employee, 'l10n_hn_biweekly_pay_contract_first_half_only', False) and getattr(
            employee, 'l10n_hn_variable_legal_monthly', False,
        ) and not employee.isr_excluded:
            snapshot = IsrConfig.compute_split_quincena_isr_snapshot(
                employee, as_of,
            ) or {}

        ytd_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('company_id', '=', company.id),
            ('state', 'in', self.PAYSLIP_CONFIRMED_STATES),
            ('credit_note', '=', False),
            ('date_to', '>=', date(year, 1, 1)),
            ('date_to', '<=', as_of),
        ])
        ytd_salary = self._line_sum(ytd_payslips, 'BASIC')
        ytd_commission = self._commission_total(ytd_payslips)
        ytd_ihss = abs(self._line_sum(ytd_payslips, 'IHSS_EMP'))
        ytd_rap = abs(self._line_sum(ytd_payslips, 'RAP_FOVIIF_EMP'))
        ytd_isr = abs(self._line_sum(ytd_payslips, 'ISR'))

        vals = {
            'amount_salary': amount_salary,
            'amount_commission': amount_commission,
            'amount_gross_month': amount_gross_month,
            'amount_ihss_month': amount_ihss_month,
            'amount_rap_month': amount_rap_month,
            'amount_isr_withheld_month': amount_isr_withheld_month,
            'ytd_gross': ytd_salary + ytd_commission,
            'ytd_ihss': ytd_ihss,
            'ytd_rap': ytd_rap,
            'ytd_isr_withheld': ytd_isr,
            'projected_salary_annual': snapshot.get('projected_salary_annual', 0.0),
            'projected_commission_ytd': snapshot.get('bonuses_ytd', ytd_commission),
            'amount_medical_credit': snapshot.get('medical_expenses', 0.0),
            'amount_other_credits': snapshot.get('other_credits', 0.0),
            'amount_total_credits': snapshot.get('deductions_total', 0.0),
            'amount_net_taxable': snapshot.get('taxable_base', 0.0),
            'amount_isr_annual': snapshot.get('isr_annual', 0.0),
            'amount_isr_target_ytd': snapshot.get('isr_target_ytd', 0.0),
            'amount_isr_balance': snapshot.get('isr_balance', 0.0),
            'payslip_ids': [(6, 0, payslips.ids)],
        }

        if existing:
            existing.write(vals)
            return existing

        vals.update({
            'employee_id': employee.id,
            'company_id': company.id,
            'year': year,
            'month': month,
        })
        return self.create(vals)

    @api.model
    def regenerate_year(self, employee, year=None, company=None):
        year = year or fields.Date.today().year
        records = self.env[self._name]
        for month in range(1, 13):
            rec = self.regenerate_month(employee, year, month, company=company)
            if rec:
                records |= rec
        return records
