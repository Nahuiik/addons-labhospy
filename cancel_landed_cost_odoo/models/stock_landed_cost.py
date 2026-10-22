# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.tools.float_utils import float_compare


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    is_cancel = fields.Boolean(
        string="Cancelled",
        default=False,
        help="Hides the Cancel button on the form after it has been used once.",
    )

    def _revert_average_standard_price_and_cleanup_history(self, line):
        """Revert AVCO standard price and remove product.value created by the price write."""
        product = line.move_id.product_id
        if product.cost_method != "average":
            return
        new_price = product.standard_price - line.additional_landed_cost
        product.write({"standard_price": new_price})
        company = product.company_id or self.env.company
        rounding = company.currency_id.rounding
        su_env = self.env(su=True)
        pv = su_env["product.value"].search(
            [
                ("product_id", "=", product.id),
                ("move_id", "=", False),
                ("lot_id", "=", False),
                ("company_id", "=", company.id),
            ],
            order="date desc, id desc",
            limit=1,
        )
        if pv and float_compare(pv.value, new_price, precision_rounding=rounding) == 0:
            pv.unlink()

    def _unlink_svls_linked_to_landed_cost(self):
        """Remove SVLs linked on the LC record when the field exists (not all DBs have it)."""
        self.ensure_one()
        if "stock.valuation.layer" not in self.env:
            return
        if "stock_valuation_layer_ids" not in self._fields:
            return
        svl = self.stock_valuation_layer_ids
        if not svl:
            return
        self.env(su=True)["stock.valuation.layer"].browse(svl.ids).unlink()

    def _purge_landed_cost_accounting_and_adjustments(self):
        """Remove journal entry, adjustment lines and valuation layers linked to the LC."""
        self.ensure_one()
        rec = self
        su_env = self.env(su=True)
        if rec.account_move_id:
            move = su_env["account.move"].browse(rec.account_move_id.ids)
            move.write({"state": "draft", "name": _("Delete sequence number")})
            move.line_ids.unlink()
            move.unlink()
        if rec.valuation_adjustment_lines:
            rec.valuation_adjustment_lines.unlink()
        rec._unlink_svls_linked_to_landed_cost()

    def action_landed_cost_cancel(self):
        for rec in self:
            for line in rec.valuation_adjustment_lines.filtered(lambda l: l.move_id):
                rec._revert_average_standard_price_and_cleanup_history(line)
            rec._purge_landed_cost_accounting_and_adjustments()
            rec.write({"state": "cancel"})

    def action_landed_cost_reset_and_cancel(self):
        for rec in self:
            for line in rec.valuation_adjustment_lines.filtered(lambda l: l.move_id):
                rec._revert_average_standard_price_and_cleanup_history(line)
            rec._purge_landed_cost_accounting_and_adjustments()
            rec.write({"state": "draft"})

    def action_landed_cost_cancel_and_delete(self):
        for rec in self:
            for line in rec.valuation_adjustment_lines.filtered(lambda l: l.move_id):
                rec._revert_average_standard_price_and_cleanup_history(line)
            rec._purge_landed_cost_accounting_and_adjustments()
            rec.write({"state": "cancel"})
            rec.unlink()

    def action_landed_cost_cancel_form(self):
        """Cancel from the form according to ir.config_parameter mode."""
        self.ensure_one()
        for line in self.valuation_adjustment_lines.filtered(lambda l: l.move_id):
            self._revert_average_standard_price_and_cleanup_history(line)
        self._purge_landed_cost_accounting_and_adjustments()
        landed_mode = self.env(su=True)["ir.config_parameter"].get_param(
            "cancel_landed_cost_odoo.land_cost_cancel_modes",
            "cancel",
        )
        if landed_mode == "cancel":
            self.write({"state": "cancel"})
            self.is_cancel = True
        elif landed_mode == "cancel_draft":
            self.write({"state": "draft"})
            self.is_cancel = False
        elif landed_mode == "cancel_delete":
            self.write({"state": "cancel"})
            self.unlink()
            return {
                "type": "ir.actions.client",
                "tag": "reload",
                "params": {
                    "menu_id": self.env.ref("stock_landed_costs.menu_stock_landed_cost").id,
                },
            }
        return True
