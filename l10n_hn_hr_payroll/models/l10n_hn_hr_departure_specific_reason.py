# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class L10nHnHrDepartureSpecificReason(models.Model):
    _name = 'l10n.hn.hr.departure.specific.reason'
    _description = 'Motivo específico de despido'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(default=True)
