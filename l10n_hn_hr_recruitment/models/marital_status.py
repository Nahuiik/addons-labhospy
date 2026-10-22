# -*- coding: utf-8 -*-

from odoo import fields, models


class MaritalStatus(models.Model):
    _name = 'l10n_hn_hr_recruitment.marital.status'
    _description = 'Estado civil'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(
        string='Código técnico',
        required=True,
        help='Debe coincidir con el valor histórico del campo marital para migración.',
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(default=True)

    _marital_status_code_unique = models.Constraint(
        'unique(code)',
        'El código de estado civil debe ser único.',
    )
