# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models


class GnHnVacationRule(models.Model):
    _name = 'gn.hn.vacation.rule'
    _description = 'Regla de antigüedad (vacaciones)'
    _order = 'plan_id, min_years'

    plan_id = fields.Many2one(
        'gn.hn.vacation.plan',
        string='Plan',
        required=True,
        ondelete='cascade',
    )
    min_years = fields.Integer('Antigüedad mínima (años)', required=True)
    max_years = fields.Integer(
        'Antigüedad máxima (años)',
        default=99,
        help='Use 99 para sin límite (ej: 4+ años)',
    )
    days_entitled = fields.Integer('Días de vacaciones', required=True)
    sequence = fields.Integer('Secuencia', default=10)
