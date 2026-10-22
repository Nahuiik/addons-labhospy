# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta


class SalaryAdvance(models.Model):
    """Salary Advance - Employee salary advance requests with approval workflow"""
    _name = 'salary.advance'
    _description = 'Salary Advance'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, 
                       default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                 default=lambda self: self.env.company, tracking=True)
    
    date = fields.Date(string='Request Date', required=True, default=fields.Date.today, tracking=True)
    advance_amount = fields.Float(string='Advance Amount', digits=(12, 2), required=True, tracking=True)
    
    # Get current wage from version
    current_wage = fields.Float(string='Current Monthly Wage', digits=(12, 2), 
                                compute='_compute_current_wage', store=False)
    
    # Maximum advance percentage from structure
    max_advance_percentage = fields.Float(string='Max Advance %', digits=(5, 2),
                                          compute='_compute_max_advance', store=False)
    
    max_advance_amount = fields.Float(string='Max Advance Amount', digits=(12, 2),
                                      compute='_compute_max_advance', store=False)
    
    advance_percentage = fields.Float(string='Advance %', digits=(5, 2),
                                       compute='_compute_advance_percentage', store=False)
    
    # Minimum days since last payment
    min_days_since_payment = fields.Integer(string='Min Days Since Payment',
                                            compute='_compute_min_days', store=False)
    days_since_last_payment = fields.Integer(string='Days Since Last Payment',
                                             compute='_compute_days_since_payment', store=False)
    
    # Accounting
    journal_id = fields.Many2one('account.journal', string='Journal', required=True,
                                 domain="[('type', 'in', ['bank', 'cash'])]")
    debit_account_id = fields.Many2one('account.account', string='Debit Account', required=True)
    credit_account_id = fields.Many2one('account.account', string='Credit Account', required=True)
    move_id = fields.Many2one('account.move', string='Accounting Entry', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('waiting_approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('cancel', 'Cancelled'),
        ('reject', 'Rejected'),
    ], string='State', default='draft', required=True, tracking=True)
    
    notes = fields.Text(string='Notes')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('salary.advance') or _('New')
        return super().create(vals)
    
    @api.depends('employee_id')
    def _compute_current_wage(self):
        for rec in self:
            if rec.employee_id and rec.employee_id.current_version_id:
                rec.current_wage = rec.employee_id.current_version_id.wage or 0.0
            else:
                rec.current_wage = 0.0
    
    @api.depends('employee_id', 'current_wage')
    def _compute_max_advance(self):
        for rec in self:
            max_percentage = 0.0
            max_amount = 0.0
            
            if rec.employee_id and rec.employee_id.current_version_id:
                structure = rec.employee_id.current_version_id.structure_type_id
                if structure:
                    # Get max advance percentage from structure
                    max_percentage = getattr(structure, 'max_advance_percentage', 0.0) or 0.0
                    if max_percentage > 0 and rec.current_wage > 0:
                        max_amount = rec.current_wage * (max_percentage / 100.0)
            
            rec.max_advance_percentage = max_percentage
            rec.max_advance_amount = max_amount
    
    @api.depends('advance_amount', 'current_wage')
    def _compute_advance_percentage(self):
        for rec in self:
            if rec.current_wage > 0:
                rec.advance_percentage = (rec.advance_amount / rec.current_wage) * 100.0
            else:
                rec.advance_percentage = 0.0
    
    @api.depends('employee_id')
    def _compute_min_days(self):
        for rec in self:
            min_days = 0
            if rec.employee_id and rec.employee_id.current_version_id:
                structure = rec.employee_id.current_version_id.structure_type_id
                if structure:
                    min_days = getattr(structure, 'min_days_advance', 0) or 0
            rec.min_days_since_payment = min_days
    
    @api.depends('employee_id', 'date')
    def _compute_days_since_payment(self):
        for rec in self:
            days = 0
            if rec.employee_id:
                # Get last payslip date
                last_payslip = self.env['hr.payslip'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'done')
                ], order='date_to desc', limit=1)
                
                if last_payslip and last_payslip.date_to:
                    delta = rec.date - last_payslip.date_to
                    days = delta.days
            rec.days_since_last_payment = days
    
    @api.constrains('employee_id')
    def _check_employee_contract(self):
        for rec in self:
            if rec.employee_id and not rec.employee_id.current_version_id:
                raise ValidationError(_('El empleado debe tener un contrato activo.'))
    
    @api.constrains('employee_id')
    def _check_employee_address(self):
        for rec in self:
            if rec.employee_id:
                # Check if employee has address (work_contact_id)
                if not rec.employee_id.work_contact_id or not rec.employee_id.work_contact_id.street:
                    raise ValidationError(_('El empleado debe tener una dirección configurada.'))
    
    @api.constrains('advance_amount', 'max_advance_amount')
    def _check_advance_amount(self):
        for rec in self:
            if rec.max_advance_amount > 0 and rec.advance_amount > rec.max_advance_amount:
                raise ValidationError(
                    _('El monto del anticipo (%.2f) excede el máximo permitido (%.2f).') % 
                    (rec.advance_amount, rec.max_advance_amount)
                )
    
    @api.constrains('days_since_last_payment', 'min_days_since_payment')
    def _check_min_days(self):
        for rec in self:
            if rec.min_days_since_payment > 0 and rec.days_since_last_payment < rec.min_days_since_payment:
                raise ValidationError(
                    _('Deben pasar al menos %d días desde el último pago. Han pasado %d días.') % 
                    (rec.min_days_since_payment, rec.days_since_last_payment)
                )
    
    def action_submit(self):
        """Submit advance request"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se pueden enviar anticipos en estado borrador.'))
        
        # Validate before submitting
        self._check_advance_amount()
        self._check_min_days()
        
        self.state = 'submit'
        self.message_post(body=_('Anticipo enviado para aprobación.'))
    
    def action_approve(self):
        """Approve advance request and create accounting entry"""
        self.ensure_one()
        if self.state not in ('submit', 'waiting_approval'):
            raise UserError(_('Solo se pueden aprobar anticipos enviados.'))
        
        # Create accounting entry
        move_vals = {
            'date': self.date,
            'journal_id': self.journal_id.id,
            'ref': _('Anticipo Salarial: %s') % self.name,
            'line_ids': [
                (0, 0, {
                    'account_id': self.debit_account_id.id,
                    'debit': self.advance_amount,
                    'credit': 0.0,
                    'partner_id': self.employee_id.work_contact_id.id if self.employee_id.work_contact_id else False,
                    'name': _('Anticipo Salarial - %s') % self.employee_id.name,
                }),
                (0, 0, {
                    'account_id': self.credit_account_id.id,
                    'debit': 0.0,
                    'credit': self.advance_amount,
                    'partner_id': self.employee_id.work_contact_id.id if self.employee_id.work_contact_id else False,
                    'name': _('Anticipo Salarial - %s') % self.employee_id.name,
                }),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        
        self.move_id = move.id
        self.state = 'approved'
        self.message_post(body=_('Anticipo aprobado y contabilizado.'))
        
        # Create recurring concept for deduction
        self._create_advance_deduction()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Anticipo Aprobado'),
                'message': _('El anticipo ha sido aprobado y contabilizado. Se creó una deducción recurrente.'),
                'type': 'success',
            }
        }
    
    def _create_advance_deduction(self):
        """Create recurring concept for advance deduction"""
        self.ensure_one()
        if not self.employee_id:
            return
        
        # Calculate number of installments (default: deduct in next payslip)
        # Or could be configured to deduct over multiple periods
        self.env['hr.employee.recurring.concept'].create({
            'employee_id': self.employee_id.id,
            'name': _('Anticipo Salarial - %s') % self.name,
            'concept_type': 'deduction',
            'amount_type': 'fixed',
            'amount': self.advance_amount,
            'is_loan': True,
            'total_amount': self.advance_amount,
            'installments': 1,
            'date_start': self.date,
            'active': True,
        })
    
    def action_cancel(self):
        """Cancel advance request"""
        self.ensure_one()
        if self.state == 'approved':
            raise UserError(_('No se puede cancelar un anticipo aprobado. Debe revertir el asiento contable primero.'))
        
        self.state = 'cancel'
        self.message_post(body=_('Anticipo cancelado.'))
    
    def action_reject(self):
        """Reject advance request"""
        self.ensure_one()
        if self.state not in ('submit', 'waiting_approval'):
            raise UserError(_('Solo se pueden rechazar anticipos enviados.'))
        
        self.state = 'reject'
        self.message_post(body=_('Anticipo rechazado.'))
