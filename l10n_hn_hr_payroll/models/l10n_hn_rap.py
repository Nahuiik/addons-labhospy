# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nHnRapSettings(models.Model):
    """RAP Settings - Configurable parameters by year and company"""
    _name = 'l10n.hn.rap.settings'
    _description = 'RAP Settings'
    _order = 'year desc, company_id'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
    ], string='State', default='draft', required=True)
    
    # FOVIIF (Fondo de Vivienda e Inclusión Financiera) parameters
    foviif_floor_monthly = fields.Float(string='RAP Monthly Floor', required=True, digits=(12, 2),
                                         help='Monthly floor for RAP calculation (exceeds IVM ceiling)')
    foviif_employee_rate = fields.Float(string='RAP Employee Rate (%)', required=True, digits=(5, 2),
                                         default=1.5, help='Employee RAP contribution rate')
    foviif_employer_rate = fields.Float(string='RAP Employer Rate (%)', required=True, digits=(5, 2),
                                         default=1.5, help='Employer RAP contribution rate')
    
    # FRL (Fondo de Reserva Laboral) parameters
    frl_minimum_wage_high_scale = fields.Float(string='Minimum Wage High Scale', required=True, digits=(12, 2),
                                                help='Minimum wage in highest scale for FRL ceiling calculation')
    frl_ceiling_monthly = fields.Float(string='FRL Monthly Ceiling', digits=(12, 2),
                                        compute='_compute_frl_ceiling', store=True,
                                        help='Monthly ceiling for FRL (3x minimum wage high scale)')
    frl_employer_rate = fields.Float(string='FRL Employer Rate (%)', required=True, digits=(5, 2),
                                      default=4.0, help='Employer FRL contribution rate')
    
    # Application rules
    apply_first_quincena = fields.Boolean(string='Apply in First Quincena', default=True)
    apply_second_quincena = fields.Boolean(string='Apply in Second Quincena', default=True)
    
    # Accounting
    foviif_employee_account_id = fields.Many2one('account.account', string='RAP Employee Account')
    foviif_employer_account_id = fields.Many2one('account.account', string='RAP Employer Account')
    frl_employer_account_id = fields.Many2one('account.account', string='FRL Employer Account')
    
    active = fields.Boolean(string='Active', default=True)
    
    @api.depends('year', 'company_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f'RAP {rec.year} - {rec.company_id.name or "All Companies"}'
    
    @api.depends('frl_minimum_wage_high_scale')
    def _compute_frl_ceiling(self):
        """Calculate FRL ceiling as 3x minimum wage high scale"""
        for rec in self:
            rec.frl_ceiling_monthly = rec.frl_minimum_wage_high_scale * 3.0
    
    @api.constrains('year', 'company_id', 'state')
    def _check_unique_validated(self):
        for rec in self:
            if rec.state == 'validated':
                existing = self.search([
                    ('year', '=', rec.year),
                    ('company_id', '=', rec.company_id.id),
                    ('state', '=', 'validated'),
                    ('id', '!=', rec.id)
                ])
                if existing:
                    raise ValidationError(_('There can only be one validated RAP setting per year and company.'))
    
    @api.constrains('foviif_employee_rate', 'foviif_employer_rate', 'frl_employer_rate')
    def _check_rates(self):
        for rec in self:
            if rec.foviif_employee_rate < 0 or rec.foviif_employer_rate < 0:
                raise ValidationError(_('FOVIIF rates cannot be negative.'))
            if rec.frl_employer_rate < 0:
                raise ValidationError(_('FRL rate cannot be negative.'))
    
    def action_validate(self):
        """Validate RAP settings"""
        self.ensure_one()
        self.write({'state': 'validated'})
        return True
    
    def action_draft(self):
        """Set to draft"""
        self.ensure_one()
        self.write({'state': 'draft'})
        return True
    
    def get_foviif_floor_for_period(self, period_days):
        """Calculate FOVIIF floor for a specific period"""
        self.ensure_one()
        # Standard prorating rule: 30/360
        period_floor = self.foviif_floor_monthly * (period_days / 30.0)
        return round(period_floor, 2)
    
    def get_frl_ceiling_for_period(self, period_days):
        """Calculate FRL ceiling for a specific period"""
        self.ensure_one()
        # Standard prorating rule: 30/360
        period_ceiling = self.frl_ceiling_monthly * (period_days / 30.0)
        return round(period_ceiling, 2)


# RAP employee fields are added in hr_employee.py to avoid multiple inheritance
