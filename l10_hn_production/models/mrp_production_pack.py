from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class HnMrpProductionPack(models.Model):
    _name = "hn.mrp.production.pack"
    _description = "Pack de la orden de fabricación"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    production_id = fields.Many2one(
        "mrp.production",
        string="Orden de fabricación",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="production_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto pack",
        required=True,
        check_company=True,
        domain="[('hn_is_pack', '=', True), ('type', '=', 'consu')]",
    )
    product_uom_qty = fields.Float(
        string="Cantidad",
        default=1.0,
        required=True,
        digits="Product Unit of Measure",
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="UdM",
        required=True,
    )
    bom_id = fields.Many2one(
        "mrp.bom",
        string="Lista de materiales",
        readonly=True,
        copy=False,
    )
    move_ids = fields.One2many(
        "stock.move",
        "hn_pack_id",
        string="Materiales",
        copy=False,
    )
    unit_cost = fields.Monetary(
        string="Costo unitario",
        compute="_compute_costs",
        currency_field="currency_id",
    )
    total_cost = fields.Monetary(
        string="Costo",
        compute="_compute_costs",
        currency_field="currency_id",
    )
    name = fields.Char(compute="_compute_name", store=True)

    @api.depends("product_id.display_name", "product_uom_qty", "product_uom_id")
    def _compute_name(self):
        for pack in self:
            product = pack.product_id.display_name or _("Pack")
            uom = pack.product_uom_id.name or ""
            pack.name = f"{product} × {pack.product_uom_qty:g} {uom}".strip()

    @api.depends(
        "product_uom_qty",
        "move_ids.state",
        "move_ids.product_uom_qty",
        "move_ids.quantity",
        "move_ids.product_id",
        "move_ids.product_id.standard_price",
        "move_ids.product_id.avg_cost",
    )
    def _compute_costs(self):
        for pack in self:
            moves = pack.move_ids.filtered(lambda move: move.state != "cancel")
            total = sum(moves.mapped("hn_overview_total_cost"))
            pack.total_cost = total
            qty = pack.product_uom_qty or 0.0
            pack.unit_cost = total / qty if qty else 0.0

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if not self.product_id:
            return
        self.product_uom_id = self.product_id.uom_id
        if self.production_id and float_is_zero(
            self.product_uom_qty, precision_rounding=self.product_id.uom_id.rounding
        ):
            self.product_uom_qty = self.production_id.product_qty or 1.0

    @api.constrains("product_id", "product_uom_qty")
    def _check_pack(self):
        for pack in self:
            if not pack.product_id.hn_is_pack:
                raise UserError(
                    _(
                        "«%(product)s» no está marcado como producto pack.",
                        product=pack.product_id.display_name,
                    )
                )
            rounding = pack.product_uom_id.rounding or pack.product_id.uom_id.rounding
            if float_compare(pack.product_uom_qty, 0.0, precision_rounding=rounding) <= 0:
                raise UserError(
                    _(
                        "Indique una cantidad mayor a cero para el pack «%(product)s».",
                        product=pack.product_id.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("product_id") and not vals.get("product_uom_id"):
                product = self.env["product.product"].browse(vals["product_id"])
                vals["product_uom_id"] = product.uom_id.id
        records = super().create(vals_list)
        records._sync_component_moves()
        return records

    def write(self, vals):
        if {"product_id", "product_uom_qty", "product_uom_id"} & set(vals):
            locked = self.move_ids.filtered(lambda move: move.state == "done")
            if locked:
                raise UserError(
                    _(
                        "No puede modificar el pack porque sus materiales ya se consumieron."
                    )
                )
        res = super().write(vals)
        if {"product_id", "product_uom_qty", "product_uom_id"} & set(vals):
            self._sync_component_moves()
        return res

    def unlink(self):
        if self.move_ids.filtered(lambda move: move.state == "done"):
            raise UserError(
                _("No puede quitar el pack porque sus materiales ya se consumieron.")
            )
        self._remove_component_moves()
        return super().unlink()

    def _find_bom(self):
        self.ensure_one()
        production = self.production_id
        Bom = self.env["mrp.bom"]
        bom = Bom._bom_find(
            self.product_id,
            picking_type=production.picking_type_id,
            company_id=production.company_id.id,
        )[self.product_id]
        if not bom:
            bom = Bom._bom_find(
                self.product_id,
                company_id=production.company_id.id,
            )[self.product_id]
        return bom

    def _exploded_components(self):
        """Cantidad a consumir de cada material del pack, en la UdM de la lista."""
        self.ensure_one()
        bom = self._find_bom()
        if not bom:
            raise UserError(
                _(
                    "El producto pack «%(product)s» no tiene lista de materiales. "
                    "Defina ahí los materiales que se consumen.",
                    product=self.product_id.display_name,
                )
            )
        factor = self.product_uom_id._compute_quantity(
            self.product_uom_qty,
            bom.product_uom_id,
            round=False,
        ) / bom.product_qty
        _boms, lines = bom.explode(
            self.product_id,
            factor,
            picking_type=self.production_id.picking_type_id,
        )
        components = {}
        for bom_line, line_data in lines:
            product = bom_line.product_id
            if product.type != "consu":
                continue
            key = (product.id, bom_line.product_uom_id.id)
            bucket = components.setdefault(
                key,
                {
                    "product": product,
                    "uom": bom_line.product_uom_id,
                    "qty": 0.0,
                },
            )
            bucket["qty"] += line_data["qty"]
        if not components:
            raise UserError(
                _(
                    "La lista de materiales de «%(product)s» no tiene componentes para consumir.",
                    product=self.product_id.display_name,
                )
            )
        return bom, components

    def _sync_component_moves(self):
        if self.env.context.get("hn_skip_pack_sync"):
            return
        for pack in self:
            production = pack.production_id
            if not production or production.state in ("done", "cancel"):
                continue
            if not production.location_src_id or not production.product_id:
                continue
            if not pack.product_id:
                continue
            bom, components = pack._exploded_components()
            if pack.bom_id != bom:
                pack.with_context(hn_skip_pack_sync=True).bom_id = bom
            existing = pack.move_ids.filtered(lambda move: move.state != "cancel")
            used_ids = set()
            Move = self.env["stock.move"]
            for component in components.values():
                product = component["product"]
                uom = component["uom"]
                qty = component["qty"]
                move = existing.filtered(
                    lambda item, pid=product.id, uid=uom.id: (
                        item.product_id.id == pid
                        and item.product_uom.id == uid
                        and item.id not in used_ids
                        and item.state != "done"
                    )
                )[:1]
                if move:
                    used_ids.add(move.id)
                    rounding = uom.rounding or 0.0001
                    if (
                        float_compare(
                            move.product_uom_qty, qty, precision_rounding=rounding
                        )
                        != 0
                    ):
                        move.write({"product_uom_qty": qty})
                    continue
                vals = production._get_move_raw_values(product, qty, uom)
                vals.update(
                    {
                        "hn_pack_id": pack.id,
                        "bom_line_id": False,
                    }
                )
                created = Move.with_context(skip_compute_move_raw_ids=True).create(vals)
                used_ids.add(created.id)
            obsolete = existing.filtered(
                lambda move: move.id not in used_ids and move.state != "done"
            )
            if obsolete:
                pack._cancel_and_unlink_moves(obsolete)
            if production.state not in ("draft", "done", "cancel"):
                production._autoconfirm_production()

    def _remove_component_moves(self):
        moves = self.move_ids.filtered(lambda move: move.state != "cancel")
        self._cancel_and_unlink_moves(moves)

    def _cancel_and_unlink_moves(self, moves):
        if not moves:
            return
        if moves.filtered(lambda move: move.state == "done"):
            raise UserError(
                _("No puede quitar materiales del pack que ya se consumieron.")
            )
        active = moves.filtered(lambda move: move.state not in ("draft", "cancel"))
        if active:
            active._action_cancel()
        moves.exists().filtered(lambda move: move.state in ("draft", "cancel")).unlink()
