# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrDisabilityType(models.Model):
    """Catálogo de tipos de discapacidad (empleados)."""
    _name = 'hr.disability.type'
    _description = 'Tipo de discapacidad'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'El nombre del tipo de discapacidad debe ser único.',
    )
