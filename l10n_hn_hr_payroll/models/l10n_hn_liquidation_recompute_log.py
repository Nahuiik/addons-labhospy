# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class L10nHnLiquidationRecomputeLog(models.Model):
    _name = 'l10n.hn.liquidation.recompute.log'
    _description = 'Log de recálculo de liquidación (HN)'
    _order = 'create_date desc'

    liquidation_id = fields.Many2one(
        'l10n.hn.liquidation',
        required=True,
        ondelete='cascade',
        index=True,
    )
    reason = fields.Text(string='Motivo', required=True)
    snapshot_json = fields.Text(string='Snapshot (JSON truncado)')
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda s: s.env.user, required=True)
