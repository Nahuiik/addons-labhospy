# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class L10nHnThirteenthMonth(models.Model):
    """13th Month (Aguinaldo) - Calculation and payment records"""
    _name = 'l10n.hn.thirteenth.month'
    _description = '13th Month (Aguinaldo)'
    _order = 'year desc, employee_id'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    
    # Calculation parameters
    calculation_method = fields.Selection([
        ('proportional', 'Proportional to Worked Period (30-day months)'),
    ], string='Calculation Method', required=True, default='proportional')
    
    # Period worked (fixed: January 1 to December 31)
    period_start = fields.Date(string='Period Start', compute='_compute_period_dates', store=True)
    period_end = fields.Date(string='Period End', compute='_compute_period_dates', store=True)
    worked_days = fields.Integer(string='Worked Days (30-day months)', compute='_compute_worked_days', store=True)
    total_days = fields.Integer(string='Total Days in Year', default=360, help='12 months × 30 days = 360 days')
    
    # Amounts (computed automatically, kept for reference)
    calculated_amount = fields.Float(string='Calculated Amount', digits=(12, 2),
                                     compute='_compute_calculated_amount', store=True)
    
    # Payment (must be paid before December 15)
    payment_month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Payment Month', default='12', required=True,
       help='Must be paid before December 15. December salary is inferred as fully paid.')
    
    paid = fields.Boolean(string='Paid', default=False)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', ondelete='set null')
    
    # ISR exemption (up to 10 minimum wages)
    isr_exempt_amount = fields.Float(string='ISR Exempt Amount', digits=(12, 2),
                                      help='Amount exempt from ISR (up to 10 minimum wages)')
    isr_taxable_amount = fields.Float(string='ISR Taxable Amount', digits=(12, 2),
                                      compute='_compute_isr_taxable', store=True)
    
    @api.depends('employee_id', 'year')
    def _compute_name(self):
        for rec in self:
            rec.name = f'13th Month {rec.year} - {rec.employee_id.name or ""}'
    
    @api.depends('year')
    def _compute_period_dates(self):
        """Set fixed period: January 1 to December 31 of the year"""
        for rec in self:
            if rec.year:
                rec.period_start = datetime(rec.year, 1, 1).date()
                rec.period_end = datetime(rec.year, 12, 31).date()
            else:
                rec.period_start = False
                rec.period_end = False
    
    @api.depends('employee_id', 'period_start', 'period_end', 'year')
    def _compute_worked_days(self):
        """Calculate worked days proportionally from employee start date using 30-day months"""
        for rec in self:
            if not rec.employee_id or not rec.period_start or not rec.period_end:
                rec.worked_days = 0
                continue
            
            # Get employee's first contract start date (using native hr.version)
            first_version = rec.env['hr.version'].search([
                ('employee_id', '=', rec.employee_id.id)
            ], order='contract_date_start asc', limit=1)
            
            if not first_version:
                rec.worked_days = 0
                continue
            
            employee_start_date = first_version.contract_date_start
            
            # If employee started before the period, use period start
            # If employee started during the period, use employee start date
            calculation_start = max(employee_start_date, rec.period_start)
            
            # Period end is always December 31, but we infer December will be paid fully
            # So we use December 31 as the end date
            calculation_end = rec.period_end
            
            if calculation_start > calculation_end:
                rec.worked_days = 0
                continue
            
            # Calculate days using 30-day months
            rec.worked_days = rec._calculate_days_30_day_months(calculation_start, calculation_end)
    
    def _calculate_days_30_day_months(self, start_date, end_date):
        """Calculate days between two dates using 30-day months"""
        if not start_date or not end_date or start_date > end_date:
            return 0
        
        # Calculate months and remaining days
        start_year = start_date.year
        start_month = start_date.month
        start_day = start_date.day
        
        end_year = end_date.year
        end_month = end_date.month
        end_day = end_date.day
        
        # If same month, calculate directly
        if start_year == end_year and start_month == end_month:
            days = end_day - start_day + 1
            return min(days, 30)  # Cap at 30 days per month
        
        # Calculate total months difference
        total_months = (end_year - start_year) * 12 + (end_month - start_month)
        
        # Calculate days in partial months
        # Start month: days from start_day to end of month (30-day month)
        days_start_month = 30 - start_day + 1
        
        # End month: days from start to end_day
        days_end_month = end_day
        
        # If consecutive months (difference of 1 month)
        if total_months == 1:
            days = days_start_month + days_end_month
        else:
            # Full months (30 days each) + partial months
            # Subtract 1 because we're counting partial months separately
            full_months = max(0, total_months - 1)
            days = days_start_month + (full_months * 30) + days_end_month
        
        return days
    
    def _calculate_proportional_with_salary_changes(self, period_start, period_end, employee_start_date):
        """Calculate proportional amount considering salary changes during the period"""
        if not period_start or not period_end or not employee_start_date:
            return 0.0
        
        # Get all contract versions active during the period (using native hr.version)
        versions = self.env['hr.version'].search([
            ('employee_id', '=', self.employee_id.id),
            ('contract_date_start', '<=', period_end),
            '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', period_start),
        ], order='contract_date_start asc')
        
        if not versions:
            return 0.0
        
        total_amount = 0.0
        calculation_start = max(employee_start_date, period_start)
        
        for version in versions:
            # Determine contract period within calculation period
            contract_start = max(version.contract_date_start, calculation_start)
            contract_end = min(version.contract_date_end or period_end, period_end)
            
            if contract_start > contract_end:
                continue
            
            # Calculate days for this contract period (30-day months)
            days = self._calculate_days_30_day_months(contract_start, contract_end)
            
            # Calculate proportional amount for this period
            # 13th month = 1 month salary, so: (wage / 360) * days
            period_amount = (version.wage / 360.0) * days
            total_amount += period_amount
        
        return total_amount
    
    @api.depends('calculation_method', 'employee_id', 'year', 'period_start', 'period_end', 'worked_days', 'total_days')
    def _compute_calculated_amount(self):
        for rec in self:
            if rec.calculation_method == 'proportional':
                if not rec.employee_id or not rec.period_start or not rec.period_end:
                    rec.calculated_amount = 0.0
                    continue
                
                # Get employee's first contract start date (using native hr.version)
                first_version = rec.env['hr.version'].search([
                    ('employee_id', '=', rec.employee_id.id)
                ], order='contract_date_start asc', limit=1)
                
                if not first_version:
                    rec.calculated_amount = 0.0
                    continue
                
                employee_start_date = first_version.contract_date_start
                
                # Calculate considering salary changes
                rec.calculated_amount = rec._calculate_proportional_with_salary_changes(
                    rec.period_start,
                    rec.period_end,
                    employee_start_date
                )
            else:
                rec.calculated_amount = 0.0
    
    @api.depends('calculated_amount', 'isr_exempt_amount')
    def _compute_isr_taxable(self):
        for rec in self:
            rec.isr_taxable_amount = max(0.0, rec.calculated_amount - rec.isr_exempt_amount)
    
    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        for rec in self:
            if rec.period_start and rec.period_end and rec.period_end < rec.period_start:
                raise ValidationError(_('Period end must be after period start.'))
    
    @api.model
    def generate_for_all_employees(self, year=None):
        """Generate 13th month records for all active employees for the given year"""
        if year is None:
            year = fields.Date.today().year
        
        # Get all active employees
        employees = self.env['hr.employee'].search([
            ('active', '=', True)
        ])
        
        created_count = 0
        updated_count = 0
        
        for employee in employees:
            # Check if record already exists
            existing = self.search([
                ('employee_id', '=', employee.id),
                ('year', '=', year)
            ], limit=1)
            
            if existing:
                # Update existing record (recalculate)
                existing._compute_calculated_amount()
                updated_count += 1
            else:
                # Create new record
                self.create({
                    'employee_id': employee.id,
                    'year': year,
                    'calculation_method': 'proportional',
                })
                created_count += 1
        
        return {
            'created': created_count,
            'updated': updated_count,
            'total': len(employees)
        }
    
    @api.model
    def action_generate_all(self):
        """Action method called from button to generate benefits for all employees"""
        year = fields.Date.today().year
        result = self.generate_for_all_employees(year)
        
        message = _('Proceso completado:\n')
        message += _('- Registros creados: %d\n') % result['created']
        message += _('- Registros actualizados: %d\n') % result['updated']
        message += _('- Total de empleados procesados: %d') % result['total']
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cálculo de 13° Mes'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }


class L10nHnFourteenthMonth(models.Model):
    """14th Month - Calculation and payment records"""
    _name = 'l10n.hn.fourteenth.month'
    _description = '14th Month'
    _order = 'year desc, employee_id'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    
    # Calculation parameters
    calculation_method = fields.Selection([
        ('proportional', 'Proportional to Worked Period (30-day months)'),
    ], string='Calculation Method', required=True, default='proportional')
    
    # Calculation period (July 1 of previous year to June 30 of current year)
    calculation_period_start = fields.Date(string='Calculation Period Start', compute='_compute_period_dates', store=True)
    calculation_period_end = fields.Date(string='Calculation Period End', compute='_compute_period_dates', store=True)
    
    # Amounts (computed automatically)
    calculated_amount = fields.Float(string='Calculated Amount', digits=(12, 2),
                                     compute='_compute_calculated_amount', store=True)
    
    # Payment (typically paid in June)
    payment_month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Payment Month', default='6', required=True,
       help='Typically paid in June (month 6)')
    
    paid = fields.Boolean(string='Paid', default=False)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', ondelete='set null')
    
    # ISR exemption (up to 10 minimum wages)
    isr_exempt_amount = fields.Float(string='ISR Exempt Amount', digits=(12, 2))
    isr_taxable_amount = fields.Float(string='ISR Taxable Amount', digits=(12, 2),
                                      compute='_compute_isr_taxable', store=True)
    
    @api.depends('employee_id', 'year')
    def _compute_name(self):
        for rec in self:
            rec.name = f'14th Month {rec.year} - {rec.employee_id.name or ""}'
    
    @api.depends('year')
    def _compute_period_dates(self):
        """Set period: July 1 of previous year to June 30 of current year"""
        for rec in self:
            if rec.year:
                # Previous year July 1
                rec.calculation_period_start = datetime(rec.year - 1, 7, 1).date()
                # Current year June 30
                rec.calculation_period_end = datetime(rec.year, 6, 30).date()
            else:
                rec.calculation_period_start = False
                rec.calculation_period_end = False
    
    def _calculate_days_30_day_months(self, start_date, end_date):
        """Calculate days between two dates using 30-day months"""
        if not start_date or not end_date or start_date > end_date:
            return 0
        
        # Calculate months and remaining days
        start_year = start_date.year
        start_month = start_date.month
        start_day = start_date.day
        
        end_year = end_date.year
        end_month = end_date.month
        end_day = end_date.day
        
        # If same month, calculate directly
        if start_year == end_year and start_month == end_month:
            days = end_day - start_day + 1
            return min(days, 30)  # Cap at 30 days per month
        
        # Calculate total months difference
        total_months = (end_year - start_year) * 12 + (end_month - start_month)
        
        # Calculate days in partial months
        # Start month: days from start_day to end of month (30-day month)
        days_start_month = 30 - start_day + 1
        
        # End month: days from start to end_day
        days_end_month = end_day
        
        # If consecutive months (difference of 1 month)
        if total_months == 1:
            days = days_start_month + days_end_month
        else:
            # Full months (30 days each) + partial months
            # Subtract 1 because we're counting partial months separately
            full_months = max(0, total_months - 1)
            days = days_start_month + (full_months * 30) + days_end_month
        
        return days
    
    def _calculate_proportional_with_salary_changes(self, period_start, period_end, employee_start_date):
        """Calculate proportional amount considering salary changes during the period"""
        if not period_start or not period_end or not employee_start_date:
            return 0.0
        
        # Get all contract versions active during the period (using native hr.version)
        versions = self.env['hr.version'].search([
            ('employee_id', '=', self.employee_id.id),
            ('contract_date_start', '<=', period_end),
            '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', period_start),
        ], order='contract_date_start asc')
        
        if not versions:
            return 0.0
        
        total_amount = 0.0
        calculation_start = max(employee_start_date, period_start)
        
        for version in versions:
            # Determine contract period within calculation period
            contract_start = max(version.contract_date_start, calculation_start)
            contract_end = min(version.contract_date_end or period_end, period_end)
            
            if contract_start > contract_end:
                continue
            
            # Calculate days for this contract period (30-day months)
            days = self._calculate_days_30_day_months(contract_start, contract_end)
            
            # Calculate proportional amount for this period
            # 14th month = 1 month salary, so: (wage / 360) * days
            period_amount = (version.wage / 360.0) * days
            total_amount += period_amount
        
        return total_amount
    
    @api.depends('calculation_method', 'employee_id', 'year', 'calculation_period_start', 'calculation_period_end')
    def _compute_calculated_amount(self):
        for rec in self:
            if rec.calculation_method == 'proportional':
                if not rec.employee_id or not rec.calculation_period_start or not rec.calculation_period_end:
                    rec.calculated_amount = 0.0
                    continue
                
                # Get employee's first contract start date (using native hr.version)
                first_version = rec.env['hr.version'].search([
                    ('employee_id', '=', rec.employee_id.id)
                ], order='contract_date_start asc', limit=1)
                
                if not first_version:
                    rec.calculated_amount = 0.0
                    continue
                
                employee_start_date = first_version.contract_date_start
                
                # Calculate considering salary changes
                rec.calculated_amount = rec._calculate_proportional_with_salary_changes(
                    rec.calculation_period_start,
                    rec.calculation_period_end,
                    employee_start_date
                )
            else:
                rec.calculated_amount = 0.0
    
    @api.depends('calculated_amount', 'isr_exempt_amount')
    def _compute_isr_taxable(self):
        for rec in self:
            rec.isr_taxable_amount = max(0.0, rec.calculated_amount - rec.isr_exempt_amount)
    
    @api.constrains('calculation_period_start', 'calculation_period_end')
    def _check_period(self):
        for rec in self:
            if rec.calculation_period_start and rec.calculation_period_end:
                if rec.calculation_period_end < rec.calculation_period_start:
                    raise ValidationError(_('Calculation period end must be after period start.'))
    
    @api.model
    def generate_for_all_employees(self, year=None):
        """Generate 14th month records for all active employees for the given year"""
        if year is None:
            year = fields.Date.today().year
        
        # Get all active employees
        employees = self.env['hr.employee'].search([
            ('active', '=', True)
        ])
        
        created_count = 0
        updated_count = 0
        
        for employee in employees:
            # Check if record already exists
            existing = self.search([
                ('employee_id', '=', employee.id),
                ('year', '=', year)
            ], limit=1)
            
            if existing:
                # Update existing record (recalculate)
                existing._compute_calculated_amount()
                updated_count += 1
            else:
                # Create new record
                self.create({
                    'employee_id': employee.id,
                    'year': year,
                    'calculation_method': 'proportional',
                })
                created_count += 1
        
        return {
            'created': created_count,
            'updated': updated_count,
            'total': len(employees)
        }
    
    @api.model
    def action_generate_all(self):
        """Action method called from button to generate benefits for all employees"""
        year = fields.Date.today().year
        result = self.generate_for_all_employees(year)
        
        message = _('Proceso completado:\n')
        message += _('- Registros creados: %d\n') % result['created']
        message += _('- Registros actualizados: %d\n') % result['updated']
        message += _('- Total de empleados procesados: %d') % result['total']
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cálculo de 14° Mes'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }