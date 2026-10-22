# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _


class HrSalaryRule(models.Model):
    """Extend hr.salary.rule for Honduras payroll localization"""
    _inherit = 'hr.salary.rule'
    
    # Base calculation flags
    is_ihss_base = fields.Boolean(string='IHSS Base', default=False,
                                  help='Include in IHSS calculation base')
    is_rap_base = fields.Boolean(string='RAP Base', default=False,
                                 help='Include in RAP calculation base')
    is_isr_base = fields.Boolean(string='ISR Base', default=False,
                                 help='Include in ISR taxable base')
    isr_taxable = fields.Boolean(string='ISR Taxable', default=False,
                                help='This income is taxable for ISR (e.g., bonuses, commissions)')
    isr_deductible = fields.Boolean(string='ISR Deductible', default=False,
                                   help='This deduction reduces taxable income for ISR (e.g., AFP, Colegio Profesional)')
    is_computable = fields.Boolean(string='Computable for Benefits', default=False,
                                   help='Include in 13th and 14th month calculations')
    l10n_hn_counts_as_commission = fields.Boolean(
        string='Cuenta como comisión (historial mensual)',
        default=False,
        help='Si está activo, el total de esta regla se suma como comisión al consolidar el historial '
             'salarial mensual desde recibos.',
    )
    
    # Periodicity
    periodicity = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Biweekly'),
        ('monthly', 'Monthly'),
        ('all', 'All'),
    ], string='Periodicity', default='all',
       help='Periodicity for which this rule applies')
    
    # Year applicability
    year = fields.Integer(string='Year', default=0,
                          help='Year for which this rule applies (0 for all years)')
    
    # Accounting
    account_debit = fields.Many2one('account.account', string='Debit Account')
    account_credit = fields.Many2one('account.account', string='Credit Account')


class HrPayrollStructure(models.Model):
    """Extend hr.payroll.structure for Honduras payroll localization"""
    _inherit = 'hr.payroll.structure'
    
    # Region/Assignment (optional)
    region_id = fields.Many2one('hr.region', string='Region',
                                help='Optional region/assignment for this structure')
    periodicity = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Biweekly'),
        ('monthly', 'Monthly'),
    ], string='Periodicity', required=True, default='monthly')
    
    # Year applicability
    year = fields.Integer(string='Year', default=0,
                          help='Year for which this structure applies (0 for all years)')
    
    # Company
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                  default=lambda self: self.env.company)


class HrPayrollStructureType(models.Model):
    """Sincronizar versiones HN cuando cambia default_schedule_pay (anticipo: gn_hr_payroll_salary_management)."""
    _inherit = 'hr.payroll.structure.type'

    def write(self, vals):
        """When default_schedule_pay changes, update existing versions"""
        result = super().write(vals)
        
        if 'default_schedule_pay' in vals:
            # Update all versions with this structure type
            schedule_to_periodicity = {
                'weekly': 'weekly',
                'bi-weekly': 'biweekly',
                'biweekly': 'biweekly',
                'monthly': 'monthly',
            }
            periodicity_map = {
                'weekly': 'weekly',
                'biweekly': 'bi-weekly',
                'monthly': 'monthly',
            }
            
            new_schedule_pay = vals['default_schedule_pay']
            new_periodicity = schedule_to_periodicity.get(new_schedule_pay, 'monthly')
            
            for structure_type in self:
                # Find all active versions with this structure type
                versions = self.env['hr.version'].search([
                    ('structure_type_id', '=', structure_type.id),
                ])
                
                # Update schedule_pay and periodicity for all versions
                for version in versions:
                    version.write({
                        'schedule_pay': new_schedule_pay,
                        'periodicity': new_periodicity,
                    })
        
        return result


class HrRegion(models.Model):
    """Regions/Assignments for payroll structures"""
    _name = 'hr.region'
    _description = 'HR Region/Assignment'
    
    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code')
    company_id = fields.Many2one('res.company', string='Company')
    active = fields.Boolean(string='Active', default=True)
