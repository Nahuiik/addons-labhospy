# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nHnIsrTable(models.Model):
    """ISR Tax Table - Progressive tax brackets by year and periodicity"""
    _name = 'l10n.hn.isr.table'
    _description = 'ISR Tax Table'
    _order = 'year desc, periodicity, id'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    periodicity = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Biweekly'),
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
    ], string='Periodicity', required=True, default='annual')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
    ], string='State', default='draft', required=True)
    
    # Tax brackets
    line_ids = fields.One2many('l10n.hn.isr.table.line', 'table_id', string='Tax Brackets', required=True)
    
    # Exempt amount
    exempt_amount = fields.Float(string='Exempt Amount', required=True, digits=(12, 2),
                                 help='Annual exempt amount for ISR calculation')
    
    # Medical services deduction (annual)
    medical_services_deduction = fields.Float(string='Medical Services Deduction', digits=(12, 2),
                                               default=40000.0,
                                               help='Annual deduction for medical services (L 40,000 for 2026)')
    
    active = fields.Boolean(string='Active', default=True)
    
    @api.depends('year', 'periodicity', 'company_id')
    def _compute_name(self):
        for rec in self:
            periodicity_label = dict(rec._fields['periodicity'].selection).get(rec.periodicity, rec.periodicity)
            rec.name = f'ISR {rec.year} - {periodicity_label} - {rec.company_id.name or "All Companies"}'
    
    @api.constrains('year', 'company_id', 'periodicity', 'state')
    def _check_unique_validated(self):
        for rec in self:
            if rec.state == 'validated':
                existing = self.search([
                    ('year', '=', rec.year),
                    ('company_id', '=', rec.company_id.id),
                    ('periodicity', '=', rec.periodicity),
                    ('state', '=', 'validated'),
                    ('id', '!=', rec.id)
                ])
                if existing:
                    raise ValidationError(_('There can only be one validated ISR table per year, company and periodicity.'))
    
    def action_validate(self):
        """Validate ISR table"""
        self.ensure_one()
        if not self.line_ids:
            raise ValidationError(_('ISR table must have at least one tax bracket.'))
        self.write({'state': 'validated'})
        return True
    
    def action_draft(self):
        """Set to draft"""
        self.ensure_one()
        self.write({'state': 'draft'})
        return True
    
    def calculate_isr(self, taxable_amount):
        """Calculate ISR based on taxable amount"""
        self.ensure_one()
        if taxable_amount <= self.exempt_amount:
            return 0.0
        
        # Find applicable bracket
        applicable_line = False
        for line in self.line_ids.sorted(key='min_amount', reverse=True):
            if taxable_amount >= line.min_amount:
                applicable_line = line
                break
        
        if not applicable_line:
            # Use highest bracket
            applicable_line = self.line_ids.sorted(key='min_amount', reverse=True)[0]
        
        # Calculate tax
        excess = taxable_amount - applicable_line.min_amount
        tax = applicable_line.base_tax + (excess * applicable_line.rate / 100.0)
        
        return round(tax, 2)


class L10nHnIsrTableLine(models.Model):
    """ISR Tax Table Line - Individual tax bracket"""
    _name = 'l10n.hn.isr.table.line'
    _description = 'ISR Tax Table Line'
    _order = 'min_amount'

    table_id = fields.Many2one('l10n.hn.isr.table', string='ISR Table', required=True, ondelete='cascade')
    min_amount = fields.Float(string='Minimum Amount', required=True, digits=(12, 2),
                              help='Minimum taxable amount for this bracket')
    max_amount = fields.Float(string='Maximum Amount', digits=(12, 2),
                               help='Maximum taxable amount for this bracket (0 for unlimited)')
    rate = fields.Float(string='Tax Rate (%)', required=True, digits=(5, 2),
                        help='Tax rate percentage for this bracket')
    base_tax = fields.Float(string='Base Tax', required=True, digits=(12, 2), default=0.0,
                            help='Fixed tax amount for this bracket (from previous brackets)')
    
    @api.constrains('min_amount', 'max_amount')
    def _check_amounts(self):
        for rec in self:
            if rec.max_amount > 0 and rec.max_amount <= rec.min_amount:
                raise ValidationError(_('Maximum amount must be greater than minimum amount.'))


class L10nHnIsrHistory(models.Model):
    """ISR History - Track ISR calculations per employee"""
    _name = 'l10n.hn.isr.history'
    _description = 'ISR History'
    _order = 'year desc, period_start desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    year = fields.Integer(string='Year', required=True)
    period_start = fields.Date(string='Period Start', required=True)
    period_end = fields.Date(string='Period End', required=True)
    
    taxable_base = fields.Float(string='Taxable Base', digits=(12, 2))
    deductions = fields.Float(string='Deductions', digits=(12, 2))
    net_taxable = fields.Float(string='Net Taxable', digits=(12, 2))
    isr_amount = fields.Float(string='ISR Amount', digits=(12, 2))
    isr_ytd = fields.Float(string='ISR YTD', digits=(12, 2),
                           help='ISR accumulated year to date')
    
    table_id = fields.Many2one('l10n.hn.isr.table', string='ISR Table Used')
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', ondelete='set null')


# ISR employee fields are added in hr_employee.py to avoid multiple inheritance
