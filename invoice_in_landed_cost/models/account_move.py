from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_rate = fields.Float(
        'Landed cost exchange rate',
        compute='_compute_rate',
        store=True,
    )

    @api.depends('currency_id', 'company_id', 'date')
    def _compute_rate(self):
        for move in self:
            if move.currency_id and move.company_id and move.currency_id != move.company_id.currency_id:
                conversion_date = move.date or fields.Date.context_today(move)
                move.l10n_rate = move.currency_id._get_conversion_rate(
                    move.currency_id,
                    move.company_id.currency_id,
                    move.company_id,
                    conversion_date,
                )
            else:
                move.l10n_rate = 1.0
