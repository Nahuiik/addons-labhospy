# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _


class HrEmployeeEmergencyContact(models.Model):
    """Emergency contacts for employees - allows multiple contacts per employee"""
    _name = 'hr.employee.emergency.contact'
    _description = 'Employee Emergency Contact'
    _order = 'sequence, id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    name = fields.Char(string='Nombre', required=True)
    relation_id = fields.Many2one(
        'hr.family.relation',
        string='Parentesco',
        help='Relación o parentesco con el empleado'
    )
    phone = fields.Char(string='Teléfono', required=True)
    phone_secondary = fields.Char(string='Teléfono Secundario')
    notes = fields.Text(string='Notas')
    
    @api.depends('name', 'relation_id')
    def _compute_display_name(self):
        for contact in self:
            if contact.relation_id:
                contact.display_name = f"{contact.name} ({contact.relation_id.name})"
            else:
                contact.display_name = contact.name or ''
