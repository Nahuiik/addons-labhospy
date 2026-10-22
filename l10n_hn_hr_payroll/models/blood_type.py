# -*- coding: utf-8 -*-

from odoo import fields, models


class BloodType(models.Model):
    _name = 'l10n_hn_hr_payroll.blood.type'
    _description = 'Tipo de sangre'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(
        string='Código',
        required=True,
        help='Clave técnica (p. ej. la del antiguo campo selection para migración).',
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(default=True)

    _blood_type_code_unique = models.Constraint(
        'unique(code)',
        'El código del grupo sanguíneo debe ser único.',
    )
