# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero, float_repr


class StockMove(models.Model):
    _inherit = "stock.move"

    hn_pack_id = fields.Many2one(
        "hn.mrp.production.pack",
        string="Pack",
        index=True,
        copy=False,
        ondelete="set null",
    )

    hn_overview_state = fields.Char(
        string="Estado",
        compute="_compute_hn_mo_overview_fields",
        readonly=True,
    )
    hn_overview_state_key = fields.Char(
        compute="_compute_hn_mo_overview_fields",
        readonly=True,
    )
    hn_overview_qty = fields.Float(
        string="Cantidad",
        compute="_compute_hn_mo_overview_fields",
        digits="Product Unit of Measure",
        readonly=True,
    )
    hn_overview_free_on_hand = fields.Char(
        string="Disponible / stock real",
        compute="_compute_hn_mo_overview_fields",
        readonly=True,
    )
    hn_overview_qty_reserved = fields.Float(
        string="Reservado",
        compute="_compute_hn_mo_overview_fields",
        digits="Product Unit of Measure",
        readonly=True,
    )
    hn_overview_receipt = fields.Char(
        string="Recibido",
        compute="_compute_hn_mo_overview_fields",
        readonly=True,
    )
    hn_overview_receipt_decorator = fields.Char(
        compute="_compute_hn_mo_overview_fields",
        readonly=True,
    )
    hn_overview_unit_cost = fields.Monetary(
        string="Costo unit.",
        compute="_compute_hn_mo_overview_fields",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_overview_total_cost = fields.Monetary(
        string="Costo x ctd",
        compute="_compute_hn_mo_overview_fields",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_overview_mo_cost = fields.Monetary(
        string="Costo MO",
        compute="_compute_hn_mo_overview_fields",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_overview_bom_cost = fields.Monetary(
        string="Costo BoM",
        compute="_compute_hn_mo_overview_fields",
        currency_field="company_currency_id",
        readonly=True,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )
    hn_overview_lot_id = fields.Many2one(
        "stock.lot",
        string="Lote / Serie",
        copy=False,
        check_company=True,
        domain="[('product_id', '=', product_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Lote o serie a consumir. Por defecto se propone el próximo a vencer (FEFO).",
    )
    hn_overview_lot_expiration = fields.Datetime(
        string="Vence",
        compute="_compute_hn_overview_lot_expiration",
        readonly=True,
    )
    hn_overview_can_edit_lot = fields.Boolean(
        compute="_compute_hn_overview_can_edit_lot",
    )
    hn_is_container_product = fields.Boolean(
        related="product_id.hn_container_tracking",
        readonly=True,
    )
    hn_content_consume_qty = fields.Float(
        string="Consumo contenido",
        digits="Product Unit of Measure",
        help="Cantidad del contenido del envase que consumirá esta orden "
        "(p. ej. gramos del frasco).",
    )
    hn_content_lot_remaining = fields.Float(
        string="Contenido restante lote",
        compute="_compute_hn_content_lot_remaining",
        digits="Product Unit of Measure",
        readonly=True,
    )
    hn_container_content_uom_id = fields.Many2one(
        related="product_id.hn_container_content_uom_id",
        readonly=True,
    )

    @api.depends("hn_overview_lot_id", "hn_overview_lot_id.hn_content_remaining")
    def _compute_hn_content_lot_remaining(self):
        for move in self:
            lot = move.hn_overview_lot_id
            move.hn_content_lot_remaining = (
                lot.hn_content_remaining if lot else 0.0
            )

    def _hn_content_rounding(self):
        self.ensure_one()
        uom = self.product_id.hn_container_content_uom_id
        return uom.rounding if uom else 0.0001

    def _hn_sync_content_consume_from_move_qty(self):
        for move in self.filtered(lambda m: m.product_id._hn_is_container()):
            product = move.product_id
            content_uom = product.hn_container_content_uom_id
            if move.product_uom == content_uom:
                content_qty = move.product_uom_qty
            elif move.product_uom == product.uom_id:
                content_qty = (
                    move.product_uom_qty * product.hn_container_content_qty
                )
            else:
                content_qty = move.product_uom._compute_quantity(
                    move.product_uom_qty,
                    content_uom,
                )
            move.hn_content_consume_qty = content_qty
            unit_qty = move._hn_container_unit_qty(content_qty)
            if move.product_uom != product.uom_id or move.product_uom_qty != unit_qty:
                move.with_context(hn_skip_container_sync=True).write(
                    {
                        "product_uom": product.uom_id.id,
                        "product_uom_qty": unit_qty,
                    }
                )

    def _hn_apply_content_consume_qty(self, content_qty):
        self.ensure_one()
        rounding = self._hn_content_rounding()
        unit_qty = self._hn_container_unit_qty(content_qty)
        self.with_context(hn_skip_container_sync=True).write(
            {
                "hn_content_consume_qty": content_qty,
                "product_uom": self.product_id.uom_id.id,
                "product_uom_qty": unit_qty,
            }
        )
        if self.hn_overview_lot_id and not float_is_zero(
            content_qty, precision_rounding=rounding
        ):
            self.with_context(hn_skip_overview_lot_apply=False)._hn_apply_overview_lot(
                self.hn_overview_lot_id
            )

    def _hn_container_unit_qty(self, content_qty=None):
        self.ensure_one()
        product = self.product_id
        content_qty = (
            content_qty
            if content_qty is not None
            else self.hn_content_consume_qty
        )
        capacity = product.hn_container_content_qty
        if float_is_zero(capacity, precision_rounding=0.0001):
            return 0.0
        return product.uom_id.round(content_qty / capacity)

    def _hn_validate_container_consumption(self):
        for move in self.filtered(
            lambda m: m.raw_material_production_id and m.product_id._hn_is_container()
        ):
            lot = move.hn_overview_lot_id
            if not lot:
                raise UserError(
                    _(
                        "Indique el lote del envase para «%(product)s».",
                        product=move.product_id.display_name,
                    )
                )
            lot._hn_init_container_content()
            rounding = move._hn_content_rounding()
            if float_is_zero(
                move.hn_content_consume_qty, precision_rounding=rounding
            ):
                raise UserError(
                    _(
                        "Indique la cantidad de contenido a consumir para «%(product)s».",
                        product=move.product_id.display_name,
                    )
                )
            if float_compare(
                move.hn_content_consume_qty,
                lot.hn_content_remaining,
                precision_rounding=rounding,
            ) > 0:
                raise UserError(
                    _(
                        "El lote «%(lot)s» solo tiene %(remain)s %(uom)s; "
                        "la orden requiere %(need)s.",
                        lot=lot.display_name,
                        remain=lot.hn_content_remaining,
                        need=move.hn_content_consume_qty,
                        uom=move.product_id.hn_container_content_uom_id.display_name,
                    )
                )

    def _action_done(self, cancel_backorder=False):
        container_moves = self.filtered(
            lambda m: m.raw_material_production_id
            and m.product_id._hn_is_container()
            and m.state != "done"
        )
        for move in container_moves:
            move._hn_validate_container_consumption()
        res = super()._action_done(cancel_backorder=cancel_backorder)
        for move in container_moves:
            lot = move.hn_overview_lot_id
            if lot:
                lot._hn_consume_content(move.hn_content_consume_qty)
        return res

    @api.model
    def _hn_lot_expiration(self, lot):
        if not lot:
            return False
        for attr in ("expiration_date", "use_date", "removal_date"):
            value = getattr(lot, attr, False)
            if value:
                return value
        return False

    def _hn_get_available_lots_at_location(self):
        self.ensure_one()
        lots = self.env["stock.lot"]
        if self.product_id.tracking == "none":
            return lots
        Quant = self.env["stock.quant"].sudo()
        quants = Quant._gather(
            self.product_id.with_company(self.company_id),
            self.location_id,
            strict=False,
        )
        lot_ids = []
        for quant in quants:
            free = quant.quantity - quant.reserved_quantity
            if float_is_zero(free, precision_rounding=self.product_uom.rounding):
                continue
            if quant.lot_id:
                lot_ids.append(quant.lot_id.id)
        return self.env["stock.lot"].browse(lot_ids)

    @api.depends("hn_overview_lot_id")
    def _compute_hn_overview_lot_expiration(self):
        for move in self:
            move.hn_overview_lot_expiration = move._hn_lot_expiration(
                move.hn_overview_lot_id
            )

    @api.depends("raw_material_production_id.state", "state", "product_id.tracking")
    def _compute_hn_overview_can_edit_lot(self):
        for move in self:
            production = move.raw_material_production_id
            move.hn_overview_can_edit_lot = bool(
                production
                and production.state not in ("done", "cancel")
                and move.state not in ("done", "cancel")
                and move.product_id.tracking != "none"
            )

    def _hn_suggest_fefo_lot(self):
        self.ensure_one()
        if self.product_id.tracking == "none":
            return self.env["stock.lot"]
        qty = self.product_uom_qty
        if self.product_id._hn_is_container():
            self._hn_sync_content_consume_from_move_qty()
            qty = self._hn_container_unit_qty()
        Transfer = self.env["hn.production.material.transfer"]
        allocations = Transfer._allocate_source_lots(
            self.product_id,
            self.location_id,
            self.company_id,
            qty,
        )
        for allocation in allocations:
            lot_id = allocation.get("lot_id")
            if lot_id:
                return self.env["stock.lot"].browse(lot_id)
        return self.env["stock.lot"]

    def _hn_sync_overview_lot_from_move_lines(self):
        for move in self.filtered("raw_material_production_id"):
            lines = move.move_line_ids.filtered(lambda ml: ml.lot_id and ml.quantity)
            lot = lines[:1].lot_id if lines else False
            if move.hn_overview_lot_id != lot:
                move.with_context(hn_skip_overview_lot_apply=True).hn_overview_lot_id = lot

    def _hn_apply_overview_lot(self, lot):
        self.ensure_one()
        if (
            self.product_id.tracking == "none"
            or self.state in ("done", "cancel")
            or not self.raw_material_production_id
        ):
            return False
        if not lot:
            self.move_line_ids.filtered(lambda ml: ml.lot_id).unlink()
            return True

        if lot.product_id != self.product_id:
            raise UserError(
                _(
                    "El lote «%(lot)s» no corresponde al producto «%(product)s».",
                    lot=lot.display_name,
                    product=self.product_id.display_name,
                )
            )
        available_lots = self._hn_get_available_lots_at_location()
        if available_lots and lot not in available_lots:
            raise UserError(
                _(
                    "El lote «%(lot)s» no tiene stock libre en «%(location)s».",
                    lot=lot.display_name,
                    location=self.location_id.display_name,
                )
            )

        qty = self.product_uom_qty
        rounding = self.product_uom.rounding
        if self.product_id._hn_is_container():
            self._hn_sync_content_consume_from_move_qty()
            self._hn_validate_container_consumption()
            qty = self._hn_container_unit_qty()
            rounding = self.product_id.uom_id.rounding

        if self.product_id.tracking == "serial":
            if not self.product_uom.is_zero(qty - 1.0) and qty > 1:
                raise UserError(
                    _(
                        "Para series con cantidad mayor a 1 use la pestaña Componentes "
                        "y el botón Detalles."
                    )
                )
            self.lot_ids = lot
            return True

        self.move_line_ids.filtered(lambda ml: ml.lot_id and ml.lot_id != lot).unlink()
        existing = self.move_line_ids.filtered(lambda ml: ml.lot_id == lot)
        if existing:
            existing[:1].quantity = qty
            (existing[1:] | self.move_line_ids.filtered(lambda ml: not ml.lot_id)).unlink()
            return True

        if self.state in ("confirmed", "waiting", "partially_available", "assigned"):
            self._do_unreserve()
            taken = self._update_reserved_quantity(
                qty,
                self.location_id,
                lot_id=lot,
                strict=True,
            )
            if not float_is_zero(taken, precision_rounding=rounding):
                return True

        line_vals = self._prepare_move_line_vals(quantity=qty)
        line_vals.update(
            {
                "lot_id": lot.id,
                "production_id": self.raw_material_production_id.id,
            }
        )
        self.env["stock.move.line"].create(line_vals)
        return True

    def _hn_auto_assign_fefo_lots(self):
        for move in self.filtered(
            lambda m: m.raw_material_production_id
            and m.product_id.tracking != "none"
            and m.state not in ("done", "cancel")
        ):
            if move.hn_overview_lot_id or move.move_line_ids.filtered(
                lambda ml: ml.lot_id and ml.quantity
            ):
                continue
            lot = move._hn_suggest_fefo_lot()
            if lot:
                move.with_context(hn_skip_overview_lot_apply=True).hn_overview_lot_id = lot
                move._hn_apply_overview_lot(lot)

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves.filtered("raw_material_production_id")._hn_sync_content_consume_from_move_qty()
        moves.filtered("raw_material_production_id")._hn_auto_assign_fefo_lots()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if {"product_uom_qty", "product_uom", "product_id"} & set(vals) and not self.env.context.get(
            "hn_skip_container_sync"
        ):
            self.filtered("raw_material_production_id")._hn_sync_content_consume_from_move_qty()
        if "hn_content_consume_qty" in vals and not self.env.context.get(
            "hn_skip_container_sync"
        ):
            for move in self.filtered(
                lambda m: m.raw_material_production_id and m.product_id._hn_is_container()
            ):
                move._hn_apply_content_consume_qty(move.hn_content_consume_qty)
        if (
            "hn_overview_lot_id" in vals
            and not self.env.context.get("hn_skip_overview_lot_apply")
        ):
            self._hn_apply_overview_lot(self.hn_overview_lot_id)
        if "move_line_ids" in vals:
            self._hn_sync_overview_lot_from_move_lines()
        return res

    @api.model
    def _hn_format_overview_availability(self, summary):
        qty_free = summary.get("quantity_free")
        qty_on_hand = summary.get("quantity_on_hand")
        if qty_free is False and qty_on_hand is False:
            return ""
        precision = summary.get("uom_precision", 2)
        free_txt = float_repr(qty_free or 0.0, precision)
        on_hand_txt = float_repr(qty_on_hand or 0.0, precision)
        return f"{free_txt} / {on_hand_txt}"

    @api.model
    def _hn_format_overview_receipt(self, receipt):
        if not receipt:
            return ""
        return receipt.get("display") or ""

    @api.model
    def _hn_get_move_unit_cost(self, move, summary):
        product = move.product_id
        if product.is_storable and "avg_cost" in product._fields:
            avg_cost = product.avg_cost
            if avg_cost:
                return product.uom_id._compute_price(avg_cost, move.product_uom)
        unit_cost = summary.get("unit_cost")
        if unit_cost:
            return unit_cost
        return product.uom_id._compute_price(product.standard_price, move.product_uom)

    @api.depends(
        "raw_material_production_id",
        "raw_material_production_id.state",
        "raw_material_production_id.move_raw_ids",
        "raw_material_production_id.hn_profit_margin_percent",
        "product_id",
        "product_id.avg_cost",
        "product_id.standard_price",
        "product_uom_qty",
        "quantity",
        "state",
    )
    def _compute_hn_mo_overview_fields(self):
        moves = self.filtered("raw_material_production_id")
        (self - moves).update(
            {
                "hn_overview_state": False,
                "hn_overview_state_key": False,
                "hn_overview_qty": 0.0,
                "hn_overview_free_on_hand": False,
                "hn_overview_qty_reserved": 0.0,
                "hn_overview_receipt": False,
                "hn_overview_receipt_decorator": False,
                "hn_overview_unit_cost": 0.0,
                "hn_overview_total_cost": 0.0,
                "hn_overview_mo_cost": 0.0,
                "hn_overview_bom_cost": 0.0,
            }
        )
        if not moves:
            return

        cache = {}
        for production in moves.raw_material_production_id:
            _summary, by_move, _extras = production._hn_get_overview_maps()
            cache[production.id] = by_move

        for move in moves:
            by_move = cache.get(move.raw_material_production_id.id, {})
            summary = by_move.get(move.id, {})
            move.hn_overview_state = summary.get("formatted_state") or summary.get("state") or ""
            move.hn_overview_state_key = summary.get("state") or ""
            move.hn_overview_qty = summary.get("quantity", move.product_uom_qty)
            if move.product_id._hn_is_container() and move.hn_content_consume_qty:
                content_uom = move.product_id.hn_container_content_uom_id
                move.hn_overview_qty = move.hn_content_consume_qty
                if content_uom and content_uom != move.product_uom:
                    pass
            move.hn_overview_free_on_hand = self._hn_format_overview_availability(summary)
            move.hn_overview_qty_reserved = summary.get("quantity_reserved", 0.0)
            receipt = summary.get("receipt") or {}
            move.hn_overview_receipt = self._hn_format_overview_receipt(receipt)
            move.hn_overview_receipt_decorator = receipt.get("decorator") or False
            unit_cost = self._hn_get_move_unit_cost(move, summary)
            qty = summary.get("quantity", move.product_uom_qty)
            currency = move.company_id.currency_id
            move.hn_overview_unit_cost = unit_cost
            move.hn_overview_total_cost = currency.round(unit_cost * qty)
            move.hn_overview_mo_cost = summary.get("mo_cost", 0.0)
            bom_cost = summary.get("bom_cost")
            move.hn_overview_bom_cost = bom_cost if bom_cost is not False else 0.0
