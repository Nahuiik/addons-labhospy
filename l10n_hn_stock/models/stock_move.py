# -*- coding: utf-8 -*-
from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _create_account_move(self):
        """Si no llega force_period_date (p. ej. tras validar movimiento), usar la fecha del movimiento."""
        moves = self
        if moves and not self.env.context.get("force_period_date"):
            first = moves[0]
            if first.date:
                moves = moves.with_context(
                    force_period_date=fields.Date.to_date(first.date)
                )
        return super(StockMove, moves)._create_account_move()

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        missing = moves.filtered(
            lambda m: m.state == "done"
            and not m.account_move_id
            and m.company_id.account_stock_journal_id
            and m.company_id.l10n_hn_stock_inventory_dates_enabled()
            and m._should_create_account_move()
        )
        if missing:
            missing._create_account_move()
        return moves
