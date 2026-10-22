# -*- coding: utf-8 -*-

from odoo import api, fields, models


class GnBanksUsdRateMixin(models.AbstractModel):
    """Expone un booleano para mostrar tasa solo en moneda USD (modificadores de vista)."""

    _name = 'gn.banks.usd_rate.mixin'
    _description = 'Visibilidad tasa de cambio (USD)'

    show_currency_rate = fields.Boolean(
        compute='_compute_show_currency_rate',
        string='Show exchange rate',
    )

    @api.depends('currency_id')
    def _compute_show_currency_rate(self):
        try:
            usd = self.env.ref('base.USD')
        except ValueError:
            usd = False
        usd_id = usd.id if usd else 0
        for rec in self:
            rec.show_currency_rate = bool(rec.currency_id and rec.currency_id.id == usd_id)
