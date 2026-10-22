# -*- coding: utf-8 -*-

from odoo import fields, models


class FieldOfStudy(models.Model):
    _name = 'l10n_hn_hr_recruitment.field.of.study'
    _description = 'Campo de estudio'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(default=True)
