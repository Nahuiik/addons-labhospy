# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrEmployeeReference(models.Model):
    """Personal and work references for employees"""
    _name = 'hr.employee.reference'
    _description = 'Referencia del Empleado'
    _order = 'reference_type, name'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True
    )
    reference_type = fields.Selection([
        ('personal', 'Personal'),
        ('work', 'Laboral'),
    ], string='Tipo', required=True, default='personal')
    name = fields.Char(string='Nombre', required=True)
    relation_company = fields.Char(
        string='Relación/Empresa',
        help='Relación personal o nombre de la empresa donde trabajaron juntos'
    )
    phone = fields.Char(string='Teléfono')
    time_known = fields.Char(
        string='Tiempo de Conocerlo',
        help='Ej: 5 años, 2 años y 6 meses'
    )
    notes = fields.Text(string='Notas')
