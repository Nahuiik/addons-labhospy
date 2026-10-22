# -*- coding: utf-8 -*-

from odoo import api, models

from .helpers import ensure_inventory_privilege


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _ensure_inventory_rights(self):
        return ensure_inventory_privilege(self.env)

    @api.model
    def action_view_quants(self):
        if not self._ensure_inventory_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_view_quants()

    @api.model
    def action_view_inventory(self):
        if not self._ensure_inventory_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_view_inventory()

    def action_set_inventory_quantity(self):
        if not self._ensure_inventory_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_set_inventory_quantity()

    def action_set_inventory_quantity_zero(self):
        if not self._ensure_inventory_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_set_inventory_quantity_zero()

    def action_apply_inventory(self, date=None):
        if not self._ensure_inventory_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_apply_inventory(date=date)

    def action_apply_all(self):
        if not self._ensure_inventory_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_apply_all()

    def action_reset(self):
        if not self._ensure_inventory_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_reset()

    def action_clear_inventory_quantity(self):
        if not self._ensure_inventory_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_clear_inventory_quantity()
