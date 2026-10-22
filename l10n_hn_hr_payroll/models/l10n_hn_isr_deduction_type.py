# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models


class L10nHnIsrDeductionType(models.Model):
    """Configurable deduction types for ISR employee deductions"""
    _name = 'l10n.hn.isr.deduction.type'
    _description = 'ISR Deduction Type'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True,
                       help='Technical code for programmatic use (e.g., afp, afp_nomina, colegio_profesional)')
    sequence = fields.Integer(string='Sequence', default=10)
    is_self_paid = fields.Boolean(
        string='Pagado por Cuenta Propia',
        default=True,
        help='Indica si esta deducción es pagada directamente por el empleado (no se descuenta de nómina). '
             'Si es False, la deducción se descuenta de la nómina.')
    active = fields.Boolean(string='Active', default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code)",
        "The code must be unique.",
    )
