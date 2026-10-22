# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models


class GnHnVacationSalaryMap(models.Model):
    _name = 'gn.hn.vacation.salary.map'
    _description = 'Mapeo reglas salariales para cálculo vacaciones HN'

    rule_code = fields.Char(
        string='Código regla',
        required=True,
        help='Código de la regla salarial (ej: BASIC, HRA). Coincide con hr.salary.rule.code',
    )
    rule_type = fields.Selection([
        ('ordinary', 'Ordinaria'),
        ('in_kind', 'En especie'),
        ('liberality', 'Liberalidad'),
    ], string='Tipo', required=True, default='ordinary',
       help='Ordinaria: cuenta para promedio. Liberalidad: excluir del cálculo.')
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )
