# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nHnVecinalBracket(models.Model):
    """Impuesto Vecinal Tax Brackets - Progressive brackets by year and company"""
    _name = 'l10n.hn.vecinal.bracket'
    _description = 'Impuesto Vecinal Tax Bracket'
    _order = 'year desc, company_id, sequence, amount_from'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    company_id = fields.Many2one('res.company', string='Company', 
                                 help='If empty, applies to all companies')
    amount_from = fields.Float(string='From Amount', required=True, digits=(12, 2),
                               help='Minimum amount for this bracket')
    amount_to = fields.Float(string='To Amount', digits=(12, 2),
                             help='Maximum amount for this bracket (0 or empty = no limit)')
    rate_per_mille = fields.Float(string='Rate per Mille (‰)', required=True, digits=(5, 2),
                                   help='Tax rate per thousand (e.g., 1.50 for 1.50‰)')
    sequence = fields.Integer(string='Sequence', default=10, required=True,
                              help='Order of brackets (lower = first)')
    active = fields.Boolean(string='Active', default=True)
    
    @api.depends('year', 'amount_from', 'amount_to', 'rate_per_mille', 'company_id')
    def _compute_name(self):
        """Generate bracket name"""
        for rec in self:
            to_str = f'-{rec.amount_to:,.0f}' if rec.amount_to > 0 else '+'
            company_str = f' - {rec.company_id.name}' if rec.company_id else ''
            rec.name = f'{rec.year}: {rec.amount_from:,.0f}{to_str} @ {rec.rate_per_mille}‰{company_str}'
    
    @api.constrains('amount_from', 'amount_to', 'year', 'company_id')
    def _check_overlapping_brackets(self):
        """Prevent overlapping brackets for same year+company"""
        for rec in self:
            domain = [
                ('year', '=', rec.year),
                ('id', '!=', rec.id),
                ('active', '=', True),
            ]
            if rec.company_id:
                domain.append(('company_id', 'in', [False, rec.company_id.id]))
            else:
                domain.append(('company_id', '=', False))
            
            overlapping = self.search(domain)
            for other in overlapping:
                # Check if brackets overlap
                rec_from = rec.amount_from
                rec_to = rec.amount_to if rec.amount_to > 0 else float('inf')
                other_from = other.amount_from
                other_to = other.amount_to if other.amount_to > 0 else float('inf')
                
                if not (rec_to < other_from or rec_from > other_to):
                    raise ValidationError(_(
                        'Bracket overlaps with existing bracket: %s. '
                        'Brackets cannot overlap for the same year and company.'
                    ) % other.name)
    
    @api.constrains('amount_from', 'amount_to')
    def _check_amounts(self):
        """Validate amount ranges"""
        for rec in self:
            if rec.amount_from < 0:
                raise ValidationError(_('From amount cannot be negative.'))
            if rec.amount_to > 0 and rec.amount_to <= rec.amount_from:
                raise ValidationError(_('To amount must be greater than From amount.'))
    
    @api.constrains('rate_per_mille')
    def _check_rate(self):
        """Validate rate"""
        for rec in self:
            if rec.rate_per_mille < 0:
                raise ValidationError(_('Rate per mille cannot be negative.'))
    
    def calculate_tax_for_amount(self, amount):
        """Calculate tax for a given amount within this bracket"""
        self.ensure_one()
        if amount < self.amount_from:
            return 0.0
        bracket_max = self.amount_to if self.amount_to > 0 else amount
        amount_in_bracket = min(amount, bracket_max) - self.amount_from
        if amount_in_bracket <= 0:
            return 0.0
        tax = (amount_in_bracket / 1000.0) * self.rate_per_mille
        return round(tax, 2)


class L10nHnVecinalEmployeeIncome(models.Model):
    """Employee Annual Income for Impuesto Vecinal - Previous year income"""
    _name = 'l10n.hn.vecinal.employee_income'
    _description = 'Impuesto Vecinal Employee Income'
    _order = 'year_base desc, employee_id'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True, ondelete='cascade')
    year_base = fields.Integer(string='Base Year', required=True,
                               help='Year of the income (e.g., 2025 if applying in 2026)')
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                  default=lambda self: self.env.company)
    annual_income = fields.Float(string='Annual Income', required=True, digits=(12, 2),
                                 help='Total annual income for the base year')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  related='company_id.currency_id', store=True, readonly=True)
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='State', default='draft', required=True)
    
    _unique_employee_year_company = models.Constraint(
        'UNIQUE(employee_id, year_base, company_id)',
        'Income record already exists for this employee, year and company.',
    )
    
    @api.depends('employee_id', 'year_base', 'company_id')
    def _compute_display_name(self):
        """Generate display name"""
        for rec in self:
            rec.display_name = f'{rec.employee_id.name or ""} - {rec.year_base} - {rec.company_id.name or ""}'
    
    def action_confirm(self):
        """Confirm income record"""
        self.write({'state': 'confirmed'})
        return True
    
    def action_draft(self):
        """Set to draft"""
        self.write({'state': 'draft'})
        return True
    
    @api.model
    def generate_for_active_employees(self, company_id, year_base):
        """Generate draft income records for all active employees of a company"""
        company = self.env['res.company'].browse(company_id)
        if not company.exists():
            raise ValidationError(_('Company not found.'))
        
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', '=', company_id)
        ])
        
        created_count = 0
        for employee in employees:
            existing = self.search([
                ('employee_id', '=', employee.id),
                ('year_base', '=', year_base),
                ('company_id', '=', company_id)
            ], limit=1)
            
            if not existing:
                self.create({
                    'employee_id': employee.id,
                    'year_base': year_base,
                    'company_id': company_id,
                    'annual_income': 0.0,
                    'state': 'draft',
                })
                created_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Records Generated'),
                'message': _('Created %d income records for active employees.') % created_count,
                'type': 'success',
            }
        }


class L10nHnVecinalRetentionHistory(models.Model):
    """Impuesto Vecinal Retention History - Track deductions per payslip"""
    _name = 'l10n.hn.vecinal.retention_history'
    _description = 'Impuesto Vecinal Retention History'
    _order = 'year desc, period_start desc, employee_id'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    year = fields.Integer(string='Year', required=True, index=True)
    period_start = fields.Date(string='Period Start', required=True)
    period_end = fields.Date(string='Period End', required=True)
    annual_income_base = fields.Float(string='Annual Income Base', digits=(12, 2),
                                     help='Annual income used for calculation')
    annual_tax = fields.Float(string='Annual Tax', digits=(12, 2),
                             help='Total annual tax calculated')
    period_amount = fields.Float(string='Period Amount', digits=(12, 2),
                                help='Amount deducted in this period')
    deduction_method = fields.Char(string='Deduction Method', readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', ondelete='set null', index=True)
    settings_id = fields.Many2one('l10n.hn.vecinal.settings', string='Settings Used', readonly=True)
    
    @api.depends('employee_id', 'year', 'period_start', 'period_end')
    def _compute_display_name(self):
        """Generate display name"""
        for rec in self:
            rec.display_name = f'{rec.employee_id.name or ""} - {rec.year} - {rec.period_start}'
    
    @api.model
    def create_from_payslip(self, payslip, annual_income, annual_tax, period_amount, settings):
        """Create history record from payslip calculation"""
        if not payslip.date_from or not payslip.date_to:
            return False
        
        # Check if record already exists for this payslip
        existing = self.search([
            ('payslip_id', '=', payslip.id)
        ], limit=1)
        
        if existing:
            # Update existing record
            existing.write({
                'annual_income_base': annual_income,
                'annual_tax': annual_tax,
                'period_amount': abs(period_amount),
                'deduction_method': dict(settings._fields['deduction_method'].selection).get(settings.deduction_method, ''),
                'settings_id': settings.id,
            })
            return existing
        
        return self.create({
            'employee_id': payslip.employee_id.id,
            'company_id': payslip.company_id.id,
            'year': payslip.date_to.year,
            'period_start': payslip.date_from,
            'period_end': payslip.date_to,
            'annual_income_base': annual_income,
            'annual_tax': annual_tax,
            'period_amount': abs(period_amount),  # Store as positive
            'deduction_method': dict(settings._fields['deduction_method'].selection).get(settings.deduction_method, ''),
            'payslip_id': payslip.id,
            'settings_id': settings.id,
        })


class L10nHnVecinalSettings(models.Model):
    """Impuesto Vecinal Settings - Configuration for retention"""
    _name = 'l10n.hn.vecinal.settings'
    _description = 'Impuesto Vecinal Settings'
    _order = 'year_apply desc, company_id'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    year_apply = fields.Integer(string='Application Year', required=True,
                               default=lambda self: fields.Date.today().year,
                               help='Year in which the tax will be deducted in payroll')
    income_year_base = fields.Integer(string='Income Base Year', required=True,
                                     compute='_compute_income_year_base', store=True, readonly=False,
                                     help='Year of income used for calculation (usually year_apply - 1)')
    deduction_method = fields.Selection([
        ('first_quincena_january', 'Primera Quincena de Enero (1 quincena)'),
        ('first_two_quincenas_january', 'Primeras Dos Quincenas de Enero (2 quincenas)'),
        ('first_four_quincenas', 'Primeras Cuatro Quincenas del Año (4 quincenas)'),
        ('monthly', 'Mensual (12 meses)'),
        ('biweekly_all_year', 'Quincenal Todo el Año (24 quincenas)'),
    ], string='Método de Deducción', required=True, default='first_two_quincenas_january',
       help='Cómo se prorratea el impuesto vecinal a lo largo del año')
    rounding = fields.Selection([
        ('2dec', '2 Decimals'),
        ('0dec', 'No Decimals'),
    ], string='Rounding', default='2dec', required=True)
    active = fields.Boolean(string='Active', default=True)
    
    # Related brackets for easy access (computed field)
    bracket_ids = fields.One2many('l10n.hn.vecinal.bracket', 'company_id', 
                                  string='Brackets',
                                  compute='_compute_bracket_ids', store=False)
    
    @api.depends('year_apply', 'company_id')
    def _compute_bracket_ids(self):
        """Compute related brackets for the application year"""
        for rec in self:
            rec.bracket_ids = self.env['l10n.hn.vecinal.bracket'].search([
                ('year', '=', rec.year_apply),
                ('company_id', 'in', [False, rec.company_id.id]),
            ])
    
    @api.depends('year_apply', 'company_id')
    def _compute_name(self):
        """Generate settings name"""
        for rec in self:
            rec.name = f'Impuesto Vecinal {rec.year_apply} - {rec.company_id.name or "All Companies"}'
    
    @api.depends('year_apply')
    def _compute_income_year_base(self):
        """Auto-calculate income year base as year_apply - 1"""
        for rec in self:
            if not rec.income_year_base or rec.income_year_base == rec.year_apply:
                rec.income_year_base = rec.year_apply - 1
    
    @api.constrains('year_apply', 'company_id', 'active')
    def _check_unique_active(self):
        """Only one active settings per company and year"""
        for rec in self:
            if rec.active:
                domain = [
                    ('year_apply', '=', rec.year_apply),
                    ('company_id', '=', rec.company_id.id),
                    ('active', '=', True),
                    ('id', '!=', rec.id)
                ]
                
                existing = self.search(domain)
                if existing:
                    raise ValidationError(_(
                        'There can only be one active Impuesto Vecinal setting per year and company.'
                    ))
    
    
    def action_create_default_brackets(self):
        """Create default brackets for the application year if they don't exist"""
        self.ensure_one()
        existing_brackets = self.env['l10n.hn.vecinal.bracket'].search([
            ('year', '=', self.year_apply),
            ('company_id', '=', self.company_id.id if self.company_id else False)
        ])
        
        if existing_brackets:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Brackets Already Exist'),
                    'message': _('Brackets already exist for year %d and company %s.') % (
                        self.year_apply, self.company_id.name or 'All'
                    ),
                    'type': 'warning',
                }
            }
        
        # Default brackets as specified
        default_brackets = [
            {'from': 1, 'to': 5000, 'rate': 1.50, 'seq': 10},
            {'from': 5001, 'to': 10000, 'rate': 2.00, 'seq': 20},
            {'from': 10001, 'to': 20000, 'rate': 2.50, 'seq': 30},
            {'from': 20001, 'to': 30000, 'rate': 3.00, 'seq': 40},
            {'from': 30001, 'to': 50000, 'rate': 3.50, 'seq': 50},
            {'from': 50001, 'to': 75000, 'rate': 3.75, 'seq': 60},
            {'from': 75001, 'to': 100000, 'rate': 4.00, 'seq': 70},
            {'from': 100001, 'to': 150000, 'rate': 5.00, 'seq': 80},
            {'from': 150001, 'to': 0, 'rate': 5.25, 'seq': 90},  # 0 = no limit
        ]
        
        bracket_obj = self.env['l10n.hn.vecinal.bracket']
        created_count = 0
        for bracket_data in default_brackets:
            bracket_obj.create({
                'year': self.year_apply,
                'company_id': self.company_id.id if self.company_id else False,
                'amount_from': bracket_data['from'],
                'amount_to': bracket_data['to'] if bracket_data['to'] > 0 else 0,
                'rate_per_mille': bracket_data['rate'],
                'sequence': bracket_data['seq'],
                'active': True,
            })
            created_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Brackets Created'),
                'message': _('Created %d default brackets for year %d.') % (created_count, self.year_apply),
                'type': 'success',
            }
        }
    
    def calculate_annual_tax(self, annual_income):
        """Calculate annual tax based on brackets (progressive by brackets)"""
        self.ensure_one()
        if annual_income <= 0:
            return 0.0
        
        # Get brackets for the application year (using year_apply for brackets)
        bracket_domain = [
            ('year', '=', self.year_apply),
            ('company_id', 'in', [False, self.company_id.id]),
            ('active', '=', True),
        ]
        brackets = self.env['l10n.hn.vecinal.bracket'].search(
            bracket_domain, order='sequence, amount_from'
        )
        
        if not brackets:
            # Log warning but return 0
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning('No brackets found for year %d and company %s', 
                          self.year_apply, self.company_id.name)
            return 0.0
        
        total_tax = 0.0
        
        # Process brackets in order
        for bracket in brackets:
            bracket_from = bracket.amount_from
            bracket_to = bracket.amount_to if bracket.amount_to > 0 else annual_income
            
            # Skip if income is below this bracket
            if annual_income < bracket_from:
                continue
            
            # Calculate income within this bracket
            income_in_bracket = min(annual_income, bracket_to) - bracket_from + 1
            if income_in_bracket <= 0:
                continue
            
            # Calculate tax for this bracket: (income / 1000) * rate_per_mille
            tax_in_bracket = (income_in_bracket / 1000.0) * bracket.rate_per_mille
            total_tax += tax_in_bracket
            
            # If we've reached the top bracket (no limit), we're done
            if bracket.amount_to == 0 or annual_income <= bracket_to:
                break
        
        # Apply rounding
        if self.rounding == '2dec':
            return round(total_tax, 2)
        else:
            return round(total_tax, 0)
    
    def get_period_amount(self, annual_tax, payslip_date_from, payslip_date_to):
        """Calculate the deduction amount for a specific payslip period"""
        self.ensure_one()
        if annual_tax <= 0:
            return 0.0
        
        if not payslip_date_from or not payslip_date_to:
            return 0.0
        
        year = payslip_date_from.year
        month = payslip_date_from.month
        day_from = payslip_date_from.day
        
        # Determine if this is first or second half of the month
        # First half: days 1-15, Second half: days 16-end
        is_first_half = day_from <= 15
        
        # Calculate quincena number for the year
        # Quincena 1: Jan 1-15, Quincena 2: Jan 16-31, Quincena 3: Feb 1-15, etc.
        year_start = date(year, 1, 1)
        days_elapsed = (payslip_date_from - year_start).days
        
        # More accurate quincena calculation
        # Each month has 2 quincenas
        quincena_number = ((month - 1) * 2) + (2 if not is_first_half else 1)
        
        # Apply deduction method
        if self.deduction_method == 'first_quincena_january':
            # Only first quincena of January (quincena 1: Jan 1-15)
            if year == payslip_date_from.year and month == 1 and is_first_half:
                return -round(annual_tax, 2)  # Full annual amount
            return 0.0
        
        elif self.deduction_method == 'first_two_quincenas_january':
            # First two quincenas of January (quincenas 1 and 2: Jan 1-15 and Jan 16-31)
            if year == payslip_date_from.year and month == 1:
                return -round(annual_tax / 2.0, 2)  # Half in each quincena
            return 0.0
        
        elif self.deduction_method == 'first_four_quincenas':
            # First four quincenas of the year (Jan 1-15, Jan 16-31, Feb 1-15, Feb 16-28/29)
            if year == payslip_date_from.year and quincena_number <= 4:
                return -round(annual_tax / 4.0, 2)  # Quarter in each quincena
            return 0.0
        
        elif self.deduction_method == 'monthly':
            # Monthly throughout the year (12 months)
            if year == payslip_date_from.year:
                return -round(annual_tax / 12.0, 2)
            return 0.0
        
        elif self.deduction_method == 'biweekly_all_year':
            # Biweekly throughout the year (24 quincenas)
            if year == payslip_date_from.year:
                return -round(annual_tax / 24.0, 2)
            return 0.0
        
        return 0.0
    
    def get_period_amount_for_month(self, annual_tax, year, month):
        """Return vecinal amount for a full month (sum of first and second half).
        Used by monthly payslip rule so the rule does not need to build dates (no import in safe_eval).
        """
        self.ensure_one()
        if annual_tax <= 0 or not year or not month:
            return 0.0
        try:
            first_end = date(year, month, 15)
            second_start = date(year, month, 16)
            # Last day of month: first day of next month minus one
            if month == 12:
                next_first = date(year + 1, 1, 1)
            else:
                next_first = date(year, month + 1, 1)
            second_end = next_first - timedelta(days=1)
        except (ValueError, TypeError):
            return 0.0
        first_half = self.get_period_amount(annual_tax, date(year, month, 1), first_end)
        second_half = self.get_period_amount(annual_tax, second_start, second_end)
        return first_half + second_half
