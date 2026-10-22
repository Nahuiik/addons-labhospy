# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class InventoryAdjustment(models.Model):
    _inherit = "stock.quant"


    @api.onchange('location_id', 'product_id', 'lot_id', 'package_id', 'owner_id')
    def _onchange_location_or_product_id(self):
        vals = {}

        # Once the new line is complete, fetch the new theoretical values.
        if self.product_id and self.location_id:
            # Sanity check if a lot has been set.
            if self.lot_id:
                if self.tracking == 'none' or self.product_id != self.lot_id.product_id:
                    vals['lot_id'] = None

            quants = self._gather(
                self.product_id, self.location_id, lot_id=self.lot_id,
                package_id=self.package_id, owner_id=self.owner_id, strict=True)
            if quants:
                for quant in quants:
                    self.quantity = quant.filtered(lambda q: q.lot_id == self.lot_id).quantity
                    break

            # Special case: directly set the quantity to one for serial numbers,
            # it'll trigger `inventory_quantity` compute.
            if self.lot_id and self.tracking == 'serial':
                vals['inventory_quantity'] = 1
                vals['inventory_quantity_auto_apply'] = 1

        if vals:
            self.update(vals)

    def inventory_adjustment_cancel(self):
        for quant in self:
            move_ids = self.env["stock.move"].search(
                [
                    ("product_id", "=", quant.product_id.id),
                    ("location_id", "=", quant.location_id.id),
                    ("state", "not in", ["cancel"]),
                ],
                order="id desc", limit=1
            )
            if not move_ids:
                move_ids = self.env["stock.move"].search(
                    [
                        ("product_id", "=", quant.product_id.id),
                        ("location_dest_id", "=", quant.location_id.id),
                        ("state", "not in", ["cancel"]),
                    ],
                    order="id desc", limit=1
                )
            for move in move_ids:
                if move.location_dest_id.usage == "inventory":
                    location_id = move.location_id
                    # qty = move.quantity_done
                    qty = move.quantity
                else:
                    location_id = move.location_dest_id
                    # qty = -move.quantity_done
                    qty = -move.quantity
                if move.product_id.tracking == "none":
                    quant_id = self.env["stock.quant"].search(
                        [
                            ("product_id", "=", move.product_id.id),
                            ("location_id", "=", move.location_id.id),
                        ],
                        limit=1,
                    )
                    quant_id._update_available_quantity(move.product_id, location_id, qty)
                else:
                    for line in move.move_line_ids:
                        quant = self.env["stock.quant"].search(
                            [
                                ("product_id", "=", move.product_id.id),
                                ("location_id", "=", move.location_id.id),
                                ("lot_id", "in", move.lot_ids.ids),
                            ],
                            limit=1,
                        )
                        lot_id = line.lot_id
                    quant._update_available_quantity(move.product_id, location_id, qty, lot_id)
                # for move_line in move._get_move_lines():
                # # for move_line in move.move_line_ids():
                #     move_line.write({"state": "draft"})
                move.sudo()._action_cancel()
                account_move_id = (
                    self.env["account.move"]
                    .sudo()
                    .search([("stock_move_id", "=", move.id)], order="id desc", limit=1)
                )
                account_move_id.button_cancel()
                move.sudo().unlink()

            # self.write({"state": "cancel"})
        return


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_cancel(self):
        for move in self:
            quant_id = self.env["stock.quant"].search(
                [
                    ("product_id", "=", move.product_id.id),
                    ("location_id", "=", move.location_id.id),
                ]
            )
            if not quant_id:
                quant_id = self.env["stock.quant"].search(
                    [
                        ("product_id", "=", move.product_id.id),
                        ("location_id", "=", move.location_dest_id.id),
                    ]
                )
            if not quant_id:
                if any(move.state == "done" for move in self):
                    raise UserError(
                        _("You cannot cancel a stock move that has been set to 'Done'.")
                    )

        for move in self:
            if move.state == "cancel":
                continue
            move._do_unreserve()
            siblings_states = (
                move.move_dest_ids.mapped("move_orig_ids") - move
            ).mapped("state")
            if move.propagate_cancel:
                if all(state == "cancel" for state in siblings_states):
                    move.move_dest_ids.filtered(
                        lambda m: m.state != "done"
                    )._action_cancel()
            else:
                if all(state in ("done", "cancel") for state in siblings_states):
                    move.move_dest_ids.write({"procure_method": "make_to_stock"})
                    move.move_dest_ids.write({"move_orig_ids": [(3, move.id, 0)]})
        self.write({"state": "cancel", "move_orig_ids": [(5, 0, 0)]})
        return True

    def _do_unreserve(self):
        moves_to_unreserve = self.env["stock.move"]
        for move in self:
            if move.state == "cancel":
                continue
            if move.state == "done":
                if move.scrapped:
                    continue
                else:
                    quant_id = self.env["stock.quant"].search(
                        [
                            ("product_id", "=", move.product_id.id),
                            ("location_id", "=", move.location_id.id),
                        ]
                    )
                    if not quant_id:
                        quant_id = self.env["stock.quant"].search(
                            [
                                ("product_id", "=", move.product_id.id),
                                ("location_id", "=", move.location_dest_id.id),
                            ]
                        )
                    if self.picking_id or quant_id:
                        pass
                    else:
                        raise UserError(
                            _(
                                "You cannot unreserve a stock move that has been set to 'Done'."
                            )
                        )
            moves_to_unreserve |= move
        moves_to_unreserve.with_context(prefetch_fields=False).mapped(
            "move_line_ids"
        ).unlink()
        return True


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.ondelete(at_uninstall=False)
    def _unlink_except_done_or_cancel(self):
        pass
        # for ml in self:
        #     if ml.state in ('done', 'cancel'):
        #         raise UserError(_('You1 can not delete product moves if the picking is done. You can only correct the done quantities.'))


    def unlink(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for ml in self:
            # if ml.state in ('done', 'cancel'):
            #     raise UserError(_('You can not delete product moves if the picking is done. You can only correct the done quantities.'))

            if (
                ml.product_id.type == "product"
                and not ml.location_id.should_bypass_reservation()
                and not float_is_zero(ml.quantity, precision_digits=precision)
                # and not float_is_zero(ml.reserved_qty, precision_digits=precision)
            ):
                try:
                    self.env["stock.quant"]._update_reserved_quantity(
                        ml.product_id,
                        ml.location_id,
                        -ml.quantity,
                        # -ml.reserved_qty,
                        lot_id=ml.lot_id,
                        package_id=ml.package_id,
                        owner_id=ml.owner_id,
                        strict=True,
                    )
                except UserError:
                    if ml.lot_id:
                        self.env["stock.quant"]._update_reserved_quantity(
                            ml.product_id,
                            ml.location_id,
                            -ml.quantity,
                            # -ml.reserved_qty,
                            lot_id=False,
                            package_id=ml.package_id,
                            owner_id=ml.owner_id,
                            strict=True,
                        )
                    else:
                        raise
        moves = self.mapped("move_id")
        if moves:
            moves._recompute_state()
        return models.Model.unlink(self)
