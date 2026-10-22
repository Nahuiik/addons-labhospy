# -*- coding: utf-8 -*-

import logging

from odoo import models

from .helpers import ensure_inventory_privilege

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _ensure_onhand_rights(self):
        return ensure_inventory_privilege(self.env)

    def _compute_show_qty_update_button(self):
        super()._compute_show_qty_update_button()
        if not self._ensure_onhand_rights():
            for product in self:
                product.show_qty_update_button = False

    def action_open_quants(self):
        if not self._ensure_onhand_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_open_quants()

    def action_open_label_layout(self):
        if not self._ensure_onhand_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_open_label_layout()


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _ensure_onhand_rights(self):
        return ensure_inventory_privilege(self.env)

    def _compute_show_qty_update_button(self):
        super()._compute_show_qty_update_button()
        allowed = self._ensure_onhand_rights()
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "[apg_disable_update_qty] Compute show_qty_update_button for templates %s -> allowed=%s",
                self.ids,
                allowed,
            )
        if not allowed:
            for template in self:
                template.show_qty_update_button = False

    def _should_open_product_quants(self):
        allowed = self._ensure_onhand_rights()
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "[apg_disable_update_qty] _should_open_product_quants called for template %s (user=%s) -> allowed=%s",
                self.ids,
                self.env.user.id,
                allowed,
            )
        if not allowed:
            return False
        return super()._should_open_product_quants()

    def action_open_quants(self):
        if not self._ensure_onhand_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_open_quants()

    def action_open_label_layout(self):
        if not self._ensure_onhand_rights():
            return {"type": "ir.actions.act_window_close"}
        return super().action_open_label_layout()
