# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik - Establecer RAP por empleado

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrRap(models.Model):
    """RAP Configuration and Employee Assignment (Establecer RAP)"""
    _name = 'hr.rap'
    _description = 'RAP Configuration'
    _order = 'name ASC'

    name = fields.Char('Descripción', required=True)
    techo_rap_min = fields.Float(
        'Salario Mínimo RAP', required=True, digits=(12, 2),
        help='Salario mínimo mensual a partir del cual aplica RAP (techo IVM del IHSS)')
    techo_rap_max = fields.Float(
        'Salario Máximo RAP', digits=(12, 2),
        help='Salario máximo sujeto a RAP. 0 = sin tope')
    rap_percentage = fields.Float(
        'Porcentaje RAP (%)', required=True, default=1.5, digits=(5, 2),
        help='Porcentaje a aplicar sobre la diferencia (wage - techo_min)')
    rap_fee_max = fields.Float(
        'Cuota Máxima', digits=(12, 2),
        help='Cuota máxima mensual cuando el salario excede el techo máximo')
    pay_periodicity = fields.Selection([
        ('weekly', 'Semanal'),
        ('bi-weekly', 'Quincenal'),
        ('monthly', 'Mensual'),
    ], 'Periodicidad Pago', default='bi-weekly', required=True)
    include_in = fields.Selection([
        ('first', 'Primera quincena'),
        ('second', 'Segunda quincena'),
        ('both', 'Ambos pagos'),
    ], 'Incluir en', default='both', required=True)
    department_id = fields.Many2one('hr.department', 'Departamento')
    employee_line_ids = fields.One2many('hr.rap.employee.line', 'parent_id', 'Empleados')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('validated', 'Validado'),
    ], 'Estado', default='draft', required=True)

    def _compute_rap_fee_for_wage(self, wage):
        """Calculate monthly RAP fee for a given wage using the tier algorithm.

        Returns:
            float: monthly RAP fee
        """
        self.ensure_one()
        if wage <= self.techo_rap_min:
            return 0.0
        if self.techo_rap_max and wage > self.techo_rap_max:
            return self.rap_fee_max or 0.0
        return (wage - self.techo_rap_min) * (self.rap_percentage / 100.0)

    def _monthly_to_period(self, monthly_fee):
        """Convert monthly fee to period fee based on pay_periodicity."""
        self.ensure_one()
        if self.pay_periodicity == 'weekly':
            return round(monthly_fee / 4.0, 2)
        elif self.pay_periodicity == 'bi-weekly':
            return round(monthly_fee / 2.0, 2)
        return round(monthly_fee, 2)

    def get_employees(self):
        """Fetch employees and calculate preview RAP fees."""
        self.ensure_one()
        self.employee_line_ids.unlink()
        domain = [
            ('active', '=', True),
            ('current_version_id', '!=', False),
            ('current_version_id.wage', '>', self.techo_rap_min),
            ('rap_excluded', '=', False),
        ]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        employees = self.env['hr.employee'].search(domain)
        Line = self.env['hr.rap.employee.line']
        for emp in employees:
            v = emp.current_version_id.sudo() if emp.current_version_id else False
            wage = v.wage or 0.0 if v else 0.0
            monthly_fee = self._compute_rap_fee_for_wage(wage)
            period_fee = self._monthly_to_period(monthly_fee)
            Line.create({
                'parent_id': self.id,
                'employee_id': emp.id,
                'version_id': v.id,
                'actual_salary': wage,
                'difference': round(max(0, wage - self.techo_rap_min), 2),
                'rap_fee': round(monthly_fee, 2),
                'bi_weekly_fee': round(monthly_fee / 2.0, 2),
                'period_fee': period_fee,
            })

    def set_rap(self):
        """Assign RAP configuration and fee to each employee's contract version."""
        self.ensure_one()
        if not self.employee_line_ids:
            raise UserError(_('Debe obtener empleados antes de establecer RAP.'))
        for line in self.employee_line_ids:
            version = line.version_id
            if not version:
                version = line.employee_id.current_version_id.sudo() if line.employee_id.current_version_id else False
                line.version_id = version
            if version:
                version.rap_setup_id = self.id
                version.rap_fee = line.period_fee
        self.write({'state': 'validated'})

    def set_to_draft(self):
        self.write({'state': 'draft'})


class HrRapEmployeeLine(models.Model):
    """RAP Employee Preview Line"""
    _name = 'hr.rap.employee.line'
    _description = 'RAP Employee Line'
    _order = 'employee_id'

    parent_id = fields.Many2one('hr.rap', 'RAP', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True)
    version_id = fields.Many2one('hr.version', 'Versión Contrato')
    actual_salary = fields.Float('Salario Actual', digits=(12, 2))
    difference = fields.Float('Diferencia', digits=(12, 2),
                              help='Salario - Techo Mínimo RAP')
    rap_fee = fields.Float('Cuota RAP Mensual', digits=(12, 2))
    bi_weekly_fee = fields.Float('Cuota Quincenal', digits=(12, 2))
    period_fee = fields.Float('Cuota por Período', digits=(12, 2),
                              help='Cuota según la periodicidad configurada')
