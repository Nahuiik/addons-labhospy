# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class HrBreastfeedingHours(models.Model):
    """Breastfeeding Hours Configuration and Management"""
    _name = 'hr.breastfeeding_hours'
    _description = 'Breastfeeding Hours'
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Name', compute='_compute_name', store=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                  default=lambda self: self.env.company)
    
    # Configuration
    total_hours = fields.Integer(string='Total Hours', required=True, default=180,
                                 help='Total breastfeeding hours according to law (default: 180 hours)')
    hours_after_postnatal = fields.Integer(string='Hours After Postnatal', default=0,
                                            help='Hours after postnatal period')
    
    # Employee lines
    line_ids = fields.One2many('hr.employee.breastfeeding_hours.line', 'breastfeeding_id', string='Employee Lines')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
    ], string='State', default='draft', required=True)
    
    notes = fields.Text(string='Notes')
    
    @api.depends('date', 'company_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f'Horas de Lactancia - {rec.date} - {rec.company_id.name or ""}'
    
    def action_get_employees(self):
        """Get eligible female employees"""
        self.ensure_one()
        # Get active female employees
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('sex', '=', 'female'),  # Assuming 'female' is the value
            ('company_id', '=', self.company_id.id)
        ])
        
        existing_employee_ids = self.line_ids.mapped('employee_id').ids
        for employee in employees:
            if employee.id not in existing_employee_ids:
                self.env['hr.employee.breastfeeding_hours.line'].create({
                    'breastfeeding_id': self.id,
                    'employee_id': employee.id,
                    'total_hours': self.total_hours,
                })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Empleadas Obtenidas'),
                'message': _('Se obtuvieron %d empleadas elegibles.') % len(employees),
                'type': 'success',
            }
        }
    
    def action_validate(self):
        """Validate and create recurring concepts for breastfeeding hours"""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Debe obtener las empleadas primero.'))
        
        if self.state != 'draft':
            raise UserError(_('Solo se pueden validar registros en estado borrador.'))
        
        for line in self.line_ids:
            if not line.employee_id.current_version_id:
                raise UserError(_('La empleada %s no tiene un contrato activo.') % line.employee_id.name)
            
            # Create recurring concept (benefit) with code HL
            # Calculate dates: start date and end date for 4 installments
            start_date = line.start_date or self.date
            # Each installment is approximately monthly
            end_date = start_date + relativedelta(months=4)
            
            self.env['hr.employee.recurring.concept'].create({
                'employee_id': line.employee_id.id,
                'name': _('Horas de Lactancia - %s') % self.name,
                'concept_type': 'income',  # Benefit
                'amount_type': 'fixed',
                'amount': line.amount_per_installment,
                'date_start': start_date,
                'date_end': end_date,
                'active': True,
            })
        
        self.state = 'validated'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Horas de Lactancia Validadas'),
                'message': _('Se crearon conceptos recurrentes para %d empleadas.') % len(self.line_ids),
                'type': 'success',
            }
        }

    def action_open_breastfeeding_leave_wizard(self):
        """Abre el asistente que convierte horas legales en permisos por días con goce de sueldo."""
        self.ensure_one()
        return {
            'name': _('Lactancia: horas a días con goce de sueldo'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.breastfeeding.hours.to.leave.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_breastfeeding_id': self.id},
        }


class HrEmployeeBreastfeedingHoursLine(models.Model):
    """Employee Breastfeeding Hours Line"""
    _name = 'hr.employee.breastfeeding_hours.line'
    _description = 'Employee Breastfeeding Hours Line'
    _order = 'employee_id'
    _check_company_auto = True

    breastfeeding_id = fields.Many2one('hr.breastfeeding_hours', string='Breastfeeding Hours',
                                        required=True, ondelete='cascade')
    company_id = fields.Many2one(
        related='breastfeeding_id.company_id',
        store=True,
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        check_company=True,
        domain="[('sex', '=', 'female'), ('active', '=', True)]",
    )
    
    current_wage = fields.Float(
        string='Current Monthly Wage',
        digits=(12, 2),
        compute='_compute_current_wage',
        store=True,
    )
    hourly_rate = fields.Float(string='Hourly Rate', digits=(12, 2), compute='_compute_hourly_rate', store=True)
    
    total_hours = fields.Integer(string='Total Hours', required=True, default=180)
    total_amount = fields.Float(string='Total Amount', digits=(12, 2), compute='_compute_amounts', store=True)
    
    amount_per_installment = fields.Float(string='Amount per Installment', digits=(12, 2),
                                          compute='_compute_amounts', store=True)
    
    start_date = fields.Date(string='Start Date', default=fields.Date.today)
    end_date = fields.Date(string='End Date', compute='_compute_end_date', store=True)

    @api.depends('employee_id', 'employee_id.current_version_id', 'employee_id.current_version_id.wage')
    def _compute_current_wage(self):
        """Salario desde la versión de contrato vigente (evita que un guardado en lista borre el valor)."""
        for rec in self:
            v = rec.employee_id.current_version_id if rec.employee_id else False
            rec.current_wage = (v.wage or 0.0) if v else 0.0

    @api.depends('employee_id', 'current_wage')
    def _compute_hourly_rate(self):
        for rec in self:
            if rec.current_wage > 0:
                # Monthly salary / 30 days / 8 hours per day
                rec.hourly_rate = (rec.current_wage / 30.0) / 8.0
            else:
                rec.hourly_rate = 0.0
    
    @api.depends('hourly_rate', 'total_hours')
    def _compute_amounts(self):
        for rec in self:
            rec.total_amount = rec.hourly_rate * rec.total_hours
            rec.amount_per_installment = rec.total_amount / 4.0  # 4 installments
    
    @api.depends('start_date')
    def _compute_end_date(self):
        for rec in self:
            if rec.start_date:
                rec.end_date = rec.start_date + relativedelta(months=4)
            else:
                rec.end_date = False
    
    @api.constrains('employee_id')
    def _check_employee_female(self):
        for rec in self:
            if rec.employee_id and rec.employee_id.sex != 'female':
                raise ValidationError(
                    _('Solo pueden registrarse horas de lactancia para personal con género «Mujer» en la ficha.')
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            bid = vals.get('breastfeeding_id')
            if bid and not vals.get('total_hours'):
                br = self.env['hr.breastfeeding.hours'].browse(bid)
                vals['total_hours'] = br.total_hours
        return super().create(vals_list)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            if self.employee_id.sex != 'female':
                return {
                    'warning': {
                        'title': _('Empleado no elegible'),
                        'message': _('Las horas de lact aplican a personal mujer según normativa y criterio del registro.'),
                    }
                }
            if self.breastfeeding_id:
                self.total_hours = self.breastfeeding_id.total_hours
