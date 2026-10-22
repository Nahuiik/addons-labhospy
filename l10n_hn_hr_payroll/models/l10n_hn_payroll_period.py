# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.gn_hr_payroll_employee_extras.models.payroll_biweekly_utils import (
    biweekly_date_range,
    period_number_from_day,
    spanish_month_name,
)


class L10nHnPayrollPeriod(models.Model):
    """Payroll Period (Quincena) for Honduras bi-weekly payroll"""
    _name = 'l10n.hn.payroll.period'
    _description = 'Payroll Period (Quincena)'
    _order = 'year desc, month desc, period_number desc'
    _check_company_auto = True
    
    name = fields.Char(string='Name', compute='_compute_name', store=True, readonly=True)
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    month = fields.Integer(string='Month', required=True, default=lambda self: fields.Date.today().month)
    period_number = fields.Selection([
        ('1', 'Primera Quincena (1-15)'),
        ('2', 'Segunda Quincena (16-Último)'),
    ], string='Period Number', required=True)
    
    date_start = fields.Date(string='Start Date', compute='_compute_dates', store=True, readonly=True)
    date_end = fields.Date(string='End Date', compute='_compute_dates', store=True, readonly=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                  default=lambda self: self.env.company)
    
    payslip_run_ids = fields.One2many('hr.payslip.run', 'payroll_period_id', string='Pay Runs')

    send_payslip_email_on_validate = fields.Boolean(
        string='Correo al validar recibos',
        default=True,
        help='Si está activo, al validarse los recibos y generarse el PDF se envía el correo '
        'estándar de «nuevo recibo de nómina» a cada empleado. Desactívelo para este período '
        'si no deben recibir correo.',
    )
    
    @api.depends('year', 'month', 'period_number')
    def _compute_name(self):
        """Generate name like 'Nómina para 2do Pago enero-2026'"""
        for rec in self:
            if rec.year and rec.month and rec.period_number:
                period_text = '1er' if rec.period_number == '1' else '2do'
                month_name = spanish_month_name(rec.month)
                rec.name = f'Nómina para {period_text} Pago {month_name}-{rec.year}'
            else:
                rec.name = ''
    
    @api.depends('year', 'month', 'period_number')
    def _compute_dates(self):
        """Calculate start and end dates based on period number"""
        for rec in self:
            if rec.year and rec.month and rec.period_number:
                rec.date_start, rec.date_end = biweekly_date_range(
                    rec.year, rec.month, rec.period_number
                )
            else:
                rec.date_start = False
                rec.date_end = False
    
    @api.constrains('year', 'month', 'period_number', 'company_id')
    def _check_unique_period(self):
        """Ensure unique period per company"""
        for rec in self:
            existing = self.search([
                ('year', '=', rec.year),
                ('month', '=', rec.month),
                ('period_number', '=', rec.period_number),
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id)
            ])
            if existing:
                raise ValidationError(_('Ya existe una quincena para este periodo y empresa.'))
    
    @api.model
    def get_or_create_period(self, year, month, period_number, company_id=None):
        """Get or create a payroll period"""
        if not company_id:
            company_id = self.env.company.id
        
        period = self.search([
            ('year', '=', year),
            ('month', '=', month),
            ('period_number', '=', str(period_number)),
            ('company_id', '=', company_id)
        ], limit=1)
        
        if not period:
            period = self.create({
                'year': year,
                'month': month,
                'period_number': str(period_number),
                'company_id': company_id,
            })
        
        return period
    
    @api.model
    def get_current_period(self, company_id=None):
        """Get current payroll period based on today's date"""
        today = fields.Date.today()
        period_number = period_number_from_day(today.day)
        return self.get_or_create_period(today.year, today.month, period_number, company_id)

    @api.model
    def _cron_create_current_month_periods(self):
        """Programado día 1 de cada mes: asegura las dos quincenas HN del mes en curso por compañía."""
        today = fields.Date.today()
        companies = self.env['res.company'].sudo().search([
            '|',
            ('country_id.code', '=', 'HN'),
            ('partner_id.country_id.code', '=', 'HN'),
        ])
        for company in companies:
            self.get_or_create_period(today.year, today.month, '1', company.id)
            self.get_or_create_period(today.year, today.month, '2', company.id)
