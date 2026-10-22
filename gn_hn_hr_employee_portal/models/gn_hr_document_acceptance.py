# -*- coding: utf-8 -*-
from odoo import api, fields, models


class GnHrDocumentAcceptance(models.Model):
    _name = 'gn.hr.document.acceptance'
    _description = 'Aceptación de políticas por empleados'
    _order = 'accepted_on desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True,
    )
    policy_id = fields.Many2one(
        'gn.hr.document.policy',
        string='Política',
        required=True,
        ondelete='cascade',
    )
    accepted_on = fields.Datetime(string='Fecha de aceptación', required=True, default=fields.Datetime.now)
    accepted_by = fields.Many2one('res.users', string='Aceptado por', default=lambda self: self.env.user)
    ip = fields.Char(string='IP')
    user_agent = fields.Char(string='User Agent')

    _employee_policy_unique = models.Constraint(
        'UNIQUE(employee_id, policy_id)',
        'El empleado ya aceptó esta política.',
    )
