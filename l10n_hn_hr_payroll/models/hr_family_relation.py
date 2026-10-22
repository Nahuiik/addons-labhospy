# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrFamilyRelation(models.Model):
    """Catalog of family relations for emergency contacts"""
    _name = 'hr.family.relation'
    _description = 'Relación Familiar'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'El nombre de la relación debe ser único.'
    )
