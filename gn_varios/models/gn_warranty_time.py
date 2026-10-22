# -*- coding: utf-8 -*-

from odoo import fields, models


class GnWarrantyTime(models.Model):
    _name = 'gn.warranty.time'
    _description = 'Tiempo de Garantía'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(default=True)
