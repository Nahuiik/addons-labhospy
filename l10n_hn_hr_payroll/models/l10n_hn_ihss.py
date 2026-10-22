# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nHnIhssSettings(models.Model):
    """IHSS Settings - Configurable parameters by year and company"""
    _name = 'l10n.hn.ihss.settings'
    _description = 'IHSS Settings'
    _order = 'year desc, company_id'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
    ], string='State', default='draft', required=True)
    
    # IVM (Invalidez, Vejez y Muerte) parameters
    ivm_ceiling_monthly = fields.Float(string='IVM Monthly Ceiling', required=True, digits=(12, 2),
                                        help='Monthly ceiling for IVM contribution base')
    ivm_employer_rate = fields.Float(string='IVM Employer Rate (%)', required=True, digits=(5, 2),
                                      default=3.5, help='Employer IVM contribution rate')
    ivm_employee_rate = fields.Float(string='IVM Employee Rate (%)', required=True, digits=(5, 2),
                                     default=2.5, help='Employee IVM contribution rate')
    ivm_state_rate = fields.Float(string='IVM State Rate (%)', digits=(5, 2), default=0.5,
                                   help='State IVM contribution rate (informative only)')
    
    # EM (Enfermedad y Maternidad) parameters
    em_ceiling_monthly = fields.Float(string='EM Monthly Ceiling', required=True, digits=(12, 2),
                                       help='Monthly ceiling for EM contribution base')
    em_employer_rate = fields.Float(string='EM Employer Rate (%)', required=True, digits=(5, 2),
                                     default=1.0, help='Employer EM contribution rate')
    em_employee_rate = fields.Float(string='EM Employee Rate (%)', required=True, digits=(5, 2),
                                     default=1.0, help='Employee EM contribution rate')
    
    # Application rules
    payment_periodicity = fields.Selection([
        ('monthly', 'Mensual'),
        ('biweekly', 'Quincenal'),
    ], string='Periodicidad Pago', default='monthly', required=True,
       help='Payment periodicity for IHSS')
    
    include_in = fields.Selection([
        ('first', 'Primera Quincena'),
        ('second', 'Segunda Quincena'),
        ('both', 'Ambas Quincenas'),
    ], string='Incluir En', default='second',
       help='In which quincena(s) to include the deduction')
    
    apply_first_quincena = fields.Boolean(string='Apply in First Quincena', default=True,
                                           help='Apply deduction in first quincena of the month')
    apply_second_quincena = fields.Boolean(string='Apply in Second Quincena', default=True,
                                            help='Apply deduction in second quincena of the month')
    
    # Computed fields for display
    em_quota_monthly = fields.Float(string='Cuota ENF-MAT', digits=(12, 2),
                                     compute='_compute_quotas', store=False,
                                     help='Monthly EM employee quota')
    ivm_quota_monthly = fields.Float(string='Cuota IVM', digits=(12, 2),
                                      compute='_compute_quotas', store=False,
                                      help='Monthly IVM employee quota')
    ihss_amount_monthly = fields.Float(string='Monto IHSS', digits=(12, 2),
                                       compute='_compute_quotas', store=False,
                                       help='Total monthly IHSS amount (employee)')
    ihss_quota_biweekly = fields.Float(string='Cuota Quincenal', digits=(12, 2),
                                        compute='_compute_quotas', store=False,
                                        help='Bi-weekly IHSS quota (employee)')
    
    # Accounting
    ivm_employee_account_id = fields.Many2one('account.account', string='IVM Employee Account')
    ivm_employer_account_id = fields.Many2one('account.account', string='IVM Employer Account')
    em_employee_account_id = fields.Many2one('account.account', string='EM Employee Account')
    em_employer_account_id = fields.Many2one('account.account', string='EM Employer Account')
    
    active = fields.Boolean(string='Active', default=True)
    
    @api.depends('em_ceiling_monthly', 'em_employee_rate', 'ivm_ceiling_monthly', 'ivm_employee_rate')
    def _compute_quotas(self):
        """Calculate monthly and bi-weekly quotas"""
        for rec in self:
            # Monthly quotas (based on ceiling)
            if rec.em_ceiling_monthly and rec.em_employee_rate:
                rec.em_quota_monthly = round(rec.em_ceiling_monthly * (rec.em_employee_rate / 100.0), 2)
            else:
                rec.em_quota_monthly = 0.0
            
            if rec.ivm_ceiling_monthly and rec.ivm_employee_rate:
                rec.ivm_quota_monthly = round(rec.ivm_ceiling_monthly * (rec.ivm_employee_rate / 100.0), 2)
            else:
                rec.ivm_quota_monthly = 0.0
            
            rec.ihss_amount_monthly = rec.em_quota_monthly + rec.ivm_quota_monthly
            # Bi-weekly quota (half of monthly)
            rec.ihss_quota_biweekly = round(rec.ihss_amount_monthly / 2.0, 2)
    
    @api.onchange('include_in')
    def _onchange_include_in(self):
        """Update apply_first_quincena and apply_second_quincena based on include_in"""
        if self.include_in == 'first':
            self.apply_first_quincena = True
            self.apply_second_quincena = False
        elif self.include_in == 'second':
            self.apply_first_quincena = False
            self.apply_second_quincena = True
        elif self.include_in == 'both':
            self.apply_first_quincena = True
            self.apply_second_quincena = True
    
    @api.onchange('apply_first_quincena', 'apply_second_quincena')
    def _onchange_apply_quincenas(self):
        """Update include_in based on apply_first_quincena and apply_second_quincena"""
        if self.apply_first_quincena and self.apply_second_quincena:
            self.include_in = 'both'
        elif self.apply_first_quincena:
            self.include_in = 'first'
        elif self.apply_second_quincena:
            self.include_in = 'second'
    
    @api.depends('year', 'company_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f'IHSS {rec.year} - {rec.company_id.name or "All Companies"}'
    
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
                    raise ValidationError(_('There can only be one validated IHSS setting per year and company.'))
    
    @api.constrains('ivm_employer_rate', 'ivm_employee_rate', 'em_employer_rate', 'em_employee_rate')
    def _check_rates(self):
        for rec in self:
            if rec.ivm_employer_rate < 0 or rec.ivm_employee_rate < 0:
                raise ValidationError(_('IHSS rates cannot be negative.'))
            if rec.em_employer_rate < 0 or rec.em_employee_rate < 0:
                raise ValidationError(_('EM rates cannot be negative.'))
    
    def action_validate(self):
        """Validate IHSS settings"""
        self.ensure_one()
        self.write({'state': 'validated'})
        return True
    
    def action_draft(self):
        """Set to draft"""
        self.ensure_one()
        self.write({'state': 'draft'})
        return True
    
    def get_ceiling_for_period(self, period_days, component='ivm'):
        """Calculate ceiling for a specific period based on monthly ceiling"""
        self.ensure_one()
        if component == 'ivm':
            monthly_ceiling = self.ivm_ceiling_monthly
        elif component == 'em':
            monthly_ceiling = self.em_ceiling_monthly
        else:
            return 0.0
        
        # Standard prorating rule: 30/360
        period_ceiling = monthly_ceiling * (period_days / 30.0)
        return round(period_ceiling, 2)


# IHSS employee fields are added in hr_employee.py to avoid multiple inheritance
