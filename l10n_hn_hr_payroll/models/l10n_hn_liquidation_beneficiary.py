# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class L10nHnLiquidationBeneficiary(models.Model):
    _name = 'l10n.hn.liquidation.beneficiary'
    _description = 'Beneficiario liquidación laboral (HN)'
    _order = 'id'

    liquidation_id = fields.Many2one(
        'l10n.hn.liquidation',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Nombre', required=True)
    partner_id = fields.Many2one('res.partner', string='Contacto')
    kinship = fields.Char(string='Parentesco')
    percentage = fields.Float(string='% Distribución', digits=(5, 2))
    economic_dependency = fields.Boolean(string='Dependencia económica')
    legal_support_note = fields.Text(string='Resolución / sustento legal')
    hr_legal_notes = fields.Text(string='Observaciones RH / Legal')
