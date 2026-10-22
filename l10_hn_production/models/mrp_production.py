from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools.float_utils import float_is_zero


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    move_raw_overview_ids = fields.One2many(
        comodel_name="stock.move",
        compute="_compute_move_raw_overview_ids",
        string="Componentes (vista general)",
    )
    hn_overview_finished_state = fields.Char(
        string="Estado",
        compute="_compute_hn_overview_summary",
        readonly=True,
    )
    hn_overview_finished_state_key = fields.Char(
        compute="_compute_hn_overview_summary",
        readonly=True,
    )
    hn_overview_finished_qty = fields.Float(
        string="Cantidad",
        compute="_compute_hn_overview_summary",
        digits="Product Unit of Measure",
        readonly=True,
    )
    hn_overview_finished_free_on_hand = fields.Char(
        string="Disponible / stock real",
        compute="_compute_hn_overview_summary",
        readonly=True,
    )
    hn_overview_finished_qty_reserved = fields.Float(
        string="Reservado",
        compute="_compute_hn_overview_summary",
        digits="Product Unit of Measure",
        readonly=True,
    )
    hn_overview_finished_receipt = fields.Char(
        string="Recibido",
        compute="_compute_hn_overview_summary",
        readonly=True,
    )
    hn_overview_finished_receipt_decorator = fields.Char(
        compute="_compute_hn_overview_summary",
        readonly=True,
    )
    hn_overview_finished_unit_cost = fields.Monetary(
        string="Costo unit.",
        compute="_compute_hn_overview_summary",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_overview_finished_total_cost = fields.Monetary(
        string="Costo x ctd",
        compute="_compute_hn_overview_summary",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_overview_finished_mo_cost = fields.Monetary(
        string="Costo MO",
        compute="_compute_hn_overview_summary",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_overview_finished_bom_cost = fields.Monetary(
        string="Costo BoM",
        compute="_compute_hn_overview_summary",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_overview_unit_mo_cost = fields.Monetary(
        string="Costo unitario MO",
        compute="_compute_hn_overview_summary",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_overview_unit_bom_cost = fields.Monetary(
        string="Costo unitario BoM",
        compute="_compute_hn_overview_summary",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_profit_margin_percent = fields.Float(
        string="Margen de utilidad (%)",
        digits="Product Price",
        tracking=True,
        help="Porcentaje de utilidad sobre el costo unitario de la orden para calcular el precio de venta.",
    )
    hn_unit_cost = fields.Monetary(
        string="Costo unitario",
        compute="_compute_hn_pricing",
        currency_field="company_currency_id",
        readonly=True,
    )
    hn_sale_price = fields.Monetary(
        string="Precio de venta",
        compute="_compute_hn_pricing",
        currency_field="company_currency_id",
        readonly=True,
        help="Costo unitario de la orden × (1 + margen / 100).",
    )
    hn_overview_finished_lot_id = fields.Many2one(
        "stock.lot",
        string="Lote / Serie terminado",
        compute="_compute_hn_overview_finished_lot_id",
        inverse="_inverse_hn_overview_finished_lot_id",
        search="_search_hn_overview_finished_lot_id",
        domain="[('product_id', '=', product_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Lote o serie del producto terminado de esta orden.",
    )
    hn_overview_finished_lot_expiration = fields.Datetime(
        string="Vence",
        compute="_compute_hn_overview_finished_lot_expiration",
        readonly=True,
    )
    hn_overview_can_edit_finished_lot = fields.Boolean(
        compute="_compute_hn_overview_can_edit_finished_lot",
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )

    material_transfer_ids = fields.One2many(
        "hn.production.material.transfer",
        "production_id",
        string="Transferencias de materiales",
        copy=False,
    )
    material_transfer_count = fields.Integer(
        string="Transferencias",
        compute="_compute_material_transfer_count",
    )
    hn_can_request_material_transfer = fields.Boolean(
        string="Puede solicitar faltantes",
        compute="_compute_hn_material_shortage",
    )
    hn_material_shortage_html = fields.Html(
        string="Faltantes de materiales",
        compute="_compute_hn_material_shortage",
        sanitize=False,
    )
    hn_pack_ids = fields.One2many(
        "hn.mrp.production.pack",
        "production_id",
        string="Packs",
        copy=False,
    )
    hn_pack_move_ids = fields.Many2many(
        "stock.move",
        compute="_compute_hn_pack_move_ids",
        string="Materiales del pack",
    )
    hn_pack_cost_total = fields.Monetary(
        string="Costo total del pack",
        compute="_compute_hn_pack_cost_total",
        currency_field="company_currency_id",
    )

    def _compute_material_transfer_count(self):
        for production in self:
            production.material_transfer_count = len(
                production.material_transfer_ids
            )

    @api.depends(
        "state",
        "move_raw_ids",
        "move_raw_ids.product_uom_qty",
        "move_raw_ids.quantity",
        "move_raw_ids.state",
        "material_transfer_ids.state",
        "material_transfer_ids.line_ids.qty_to_transfer",
        "material_transfer_ids.picking_id.state",
    )
    def _compute_hn_material_shortage(self):
        Transfer = self.env["hn.production.material.transfer"]
        for production in self:
            production.hn_can_request_material_transfer = False
            production.hn_material_shortage_html = False
            if production.state in ("draft", "done", "cancel") or not production.id:
                continue
            analysis = Transfer._get_production_shortage_analysis(production)
            issues = [item for item in analysis if item["status"] != "ok"]
            if not issues:
                continue
            production.hn_can_request_material_transfer = any(
                item["status"] == "transferable" for item in issues
            )
            rows = []
            status_class = {
                "transferable": "text-success",
                "pending_transfer": "text-warning",
                "pending_approval": "text-warning",
                "pending_picking": "text-info",
                "no_bp_stock": "text-danger",
                "partial": "text-danger",
            }
            for item in issues:
                css = status_class.get(item["status"], "")
                rows.append(
                    "<li class='%s'><strong>%s</strong>: %s</li>"
                    % (
                        css,
                        item["product"].display_name,
                        item["reason"],
                    )
                )
            production.hn_material_shortage_html = (
                "<div class='alert alert-warning mb-2' role='alert'>"
                "<strong>Componentes pendientes</strong>"
                "<ul class='mb-0 ps-3'>%s</ul>"
                "</div>" % "".join(rows)
            )

    def _hn_overview_component_moves(self):
        self.ensure_one()
        moves = self.move_raw_ids
        if self.state == "done":
            moves = moves.filtered(
                lambda move: not move.product_uom.is_zero(move.quantity)
            )
        return moves

    @api.depends("state", "move_raw_ids", "move_raw_ids.quantity")
    def _compute_move_raw_overview_ids(self):
        for production in self:
            production.move_raw_overview_ids = production._hn_overview_component_moves()

    def _hn_get_overview_maps(self):
        self.ensure_one()
        report = self.env["report.mrp.report_mo_overview"]
        data = report._get_report_data(self.id)
        by_move = {}
        for move, component in zip(
            self._hn_overview_component_moves(),
            data.get("components", []),
        ):
            by_move[move.id] = component["summary"]
        return data.get("summary", {}), by_move, data.get("extras", {})

    @api.depends("lot_producing_ids")
    def _compute_hn_overview_finished_lot_id(self):
        for production in self:
            production.hn_overview_finished_lot_id = production.lot_producing_ids[:1]

    def _inverse_hn_overview_finished_lot_id(self):
        for production in self.filtered(
            lambda p: p.state not in ("done", "cancel")
            and p.product_tracking != "none"
        ):
            lot = production.hn_overview_finished_lot_id
            if production.product_tracking == "lot":
                production.lot_producing_ids = (
                    [Command.set(lot.ids)] if lot else [Command.clear()]
                )
            elif lot and production.product_qty == 1:
                production.lot_producing_ids = [Command.set(lot.ids)]
            elif not lot:
                production.lot_producing_ids = [Command.clear()]

    def _search_hn_overview_finished_lot_id(self, operator, value):
        return [("lot_producing_ids", operator, value)]

    @api.depends("hn_overview_finished_lot_id")
    def _compute_hn_overview_finished_lot_expiration(self):
        Move = self.env["stock.move"]
        for production in self:
            production.hn_overview_finished_lot_expiration = Move._hn_lot_expiration(
                production.hn_overview_finished_lot_id
            )

    @api.depends("state", "product_tracking", "product_qty", "serial_numbers_count")
    def _compute_hn_overview_can_edit_finished_lot(self):
        for production in self:
            production.hn_overview_can_edit_finished_lot = (
                production.state not in ("done", "cancel", "draft")
                and production.product_tracking != "none"
                and not (
                    production.product_tracking == "serial"
                    and production.product_qty > 1
                )
            )

    def _hn_auto_assign_finished_lot(self):
        for production in self.filtered(
            lambda p: p.state not in ("done", "cancel", "draft")
            and p.product_tracking != "none"
            and not p.lot_producing_ids
        ):
            if production.product_tracking == "serial" and production.product_qty > 1:
                continue
            production.action_generate_serial()

    @api.model
    def _hn_default_margin_from_product(self, product):
        if not product:
            return 0.0
        cost = product.avg_cost if "avg_cost" in product._fields else 0.0
        if not cost:
            cost = product.standard_price
        price = product.lst_price
        if cost and cost > 0 and price:
            return (price - cost) / cost * 100.0
        return 0.0

    @api.onchange("product_id")
    def _onchange_product_id_hn_pricing(self):
        if self.product_id:
            self.hn_profit_margin_percent = self._hn_default_margin_from_product(
                self.product_id
            )

    @api.depends(
        "hn_profit_margin_percent",
        "hn_overview_unit_mo_cost",
        "product_id",
        "product_id.avg_cost",
        "product_id.standard_price",
        "product_qty",
        "move_raw_ids",
        "move_raw_ids.product_uom_qty",
        "move_raw_ids.product_id",
        "move_raw_ids.product_id.avg_cost",
        "state",
    )
    def _compute_hn_pricing(self):
        for production in self:
            unit_cost = production.hn_overview_unit_mo_cost
            product = production.product_id
            uom = production.product_uom_id or (product.uom_id if product else False)
            if product and uom and float_is_zero(
                unit_cost, precision_rounding=uom.rounding
            ):
                avg_cost = product.avg_cost if "avg_cost" in product._fields else 0.0
                base_cost = avg_cost or product.standard_price
                unit_cost = product.uom_id._compute_price(base_cost, uom)
            margin = production.hn_profit_margin_percent or 0.0
            production.hn_unit_cost = unit_cost
            currency = production.company_currency_id or production.env.company.currency_id
            production.hn_sale_price = currency.round(
                unit_cost * (1.0 + margin / 100.0)
            )

    @api.depends(
        "state",
        "product_qty",
        "qty_produced",
        "product_id",
        "date_start",
        "date_deadline",
        "move_raw_ids",
        "move_raw_ids.product_uom_qty",
        "move_raw_ids.quantity",
        "move_raw_ids.state",
        "move_raw_ids.product_id",
        "workorder_ids",
        "workorder_ids.duration_expected",
        "workorder_ids.duration",
        "workorder_ids.workcenter_id.hn_employee_costs_hour",
    )
    def _compute_hn_overview_summary(self):
        Move = self.env["stock.move"]
        empty = {
            "hn_overview_finished_state": False,
            "hn_overview_finished_state_key": False,
            "hn_overview_finished_qty": 0.0,
            "hn_overview_finished_free_on_hand": False,
            "hn_overview_finished_qty_reserved": 0.0,
            "hn_overview_finished_receipt": False,
            "hn_overview_finished_receipt_decorator": False,
            "hn_overview_finished_unit_cost": 0.0,
            "hn_overview_finished_total_cost": 0.0,
            "hn_overview_finished_mo_cost": 0.0,
            "hn_overview_finished_bom_cost": 0.0,
            "hn_overview_unit_mo_cost": 0.0,
            "hn_overview_unit_bom_cost": 0.0,
        }
        for production in self:
            if not production.id:
                production.update(empty)
                continue
            mo_summary, _by_move, extras = production._hn_get_overview_maps()
            receipt = mo_summary.get("receipt") or {}
            production.update(
                {
                    "hn_overview_finished_state": mo_summary.get("formatted_state")
                    or mo_summary.get("state")
                    or "",
                    "hn_overview_finished_state_key": mo_summary.get("state") or "",
                    "hn_overview_finished_qty": mo_summary.get(
                        "quantity", production.product_qty
                    ),
                    "hn_overview_finished_free_on_hand": Move._hn_format_overview_availability(
                        mo_summary
                    ),
                    "hn_overview_finished_qty_reserved": mo_summary.get(
                        "quantity_reserved", 0.0
                    ),
                    "hn_overview_finished_receipt": Move._hn_format_overview_receipt(
                        receipt
                    ),
                    "hn_overview_finished_receipt_decorator": receipt.get("decorator")
                    or False,
                    "hn_overview_finished_unit_cost": extras.get("unit_mo_cost", 0.0),
                    "hn_overview_finished_total_cost": mo_summary.get("mo_cost", 0.0),
                    "hn_overview_finished_mo_cost": mo_summary.get("mo_cost", 0.0),
                    "hn_overview_finished_bom_cost": mo_summary.get("bom_cost", 0.0)
                    if mo_summary.get("bom_cost") is not False
                    else 0.0,
                    "hn_overview_unit_mo_cost": extras.get("unit_mo_cost", 0.0),
                    "hn_overview_unit_bom_cost": extras.get("unit_bom_cost", 0.0),
                }
            )

    def _hn_lot_name_reference_date(self):
        self.ensure_one()
        if self.date_start:
            return fields.Datetime.context_timestamp(self, self.date_start).date()
        return fields.Date.context_today(self)

    def _prepare_stock_lot_values(self):
        self.ensure_one()
        return {
            "product_id": self.product_id.id,
            "name": self.env["stock.lot"]._hn_next_lot_name(
                self.product_id,
                company=self.company_id,
                lot_date=self._hn_lot_name_reference_date(),
            ),
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("product_id") and "hn_profit_margin_percent" not in vals:
                product = self.env["product.product"].browse(vals["product_id"])
                vals["hn_profit_margin_percent"] = self._hn_default_margin_from_product(
                    product
                )
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if "product_id" in vals and "hn_profit_margin_percent" not in vals:
            for production in self:
                production.hn_profit_margin_percent = (
                    production._hn_default_margin_from_product(production.product_id)
                )
        return res

    def action_confirm(self):
        res = super().action_confirm()
        self._create_production_material_transfers()
        self._hn_auto_assign_finished_lot()
        self.move_raw_ids._hn_auto_assign_fefo_lots()
        return res

    def action_assign(self):
        res = super().action_assign()
        self._hn_auto_assign_finished_lot()
        self.move_raw_ids._hn_auto_assign_fefo_lots()
        created_transfers = self._hn_create_pending_material_transfers()
        notification = self._hn_notify_material_transfers_created(created_transfers)
        if notification:
            return notification
        notification = self._hn_notify_pending_material_pickings()
        if notification:
            return notification
        return res

    def button_mark_done(self):
        self.move_raw_ids.filtered(
            lambda m: m.product_id._hn_is_container()
        )._hn_validate_container_consumption()
        res = super().button_mark_done()
        if not isinstance(res, dict):
            self.filtered(lambda p: p.state == "done")._hn_update_product_sale_price()
        return res

    def _hn_update_product_sale_price(self):
        for production in self.filtered(lambda p: p.state == "done" and p.hn_sale_price):
            product = production.product_id
            if not product:
                continue
            new_price = production.product_uom_id._compute_price(
                production.hn_sale_price, product.uom_id
            )
            if product.uom_id.is_zero(new_price):
                continue
            product.with_context(l10n_hn_skip_standard_price_chatter=True).write(
                {"list_price": new_price}
            )

    def _create_production_material_transfers(self):
        self._hn_create_pending_material_transfers()

    def _hn_create_pending_material_transfers(self):
        """Genera transferencias parciales con lo transferible desde bodega principal."""
        Transfer = self.env["hn.production.material.transfer"]
        created = Transfer
        for production in self.filtered(
            lambda p: p.state not in ("done", "cancel", "draft")
        ):
            company = production.company_id
            if (
                not company.hn_production_source_warehouse_id
                or not company.hn_production_dest_warehouse_id
            ):
                continue
            transfer = Transfer.create_from_production(production)
            if transfer:
                created |= transfer
                production.message_post(
                    body=_(
                        "Se generó la transferencia de materiales %(transfer)s "
                        "con componentes disponibles en bodega principal.",
                        transfer=transfer.display_name,
                    ),
                    subtype_xmlid="mail.mt_note",
                )
        return created

    def _hn_notify_material_transfers_created(self, transfers):
        transfers = transfers.exists()
        if not transfers:
            return False
        links = [
            {
                "label": transfer.display_name,
                "url": "/odoo/%s/%s" % (transfer._name, transfer.id),
            }
            for transfer in transfers
        ]
        if len(self) == 1:
            title = _("Transferencias generadas")
            message = _(
                "Se creó una solicitud de transferencia desde bodega principal. "
                "Apruébela para mover los componentes a producción."
            )
            if len(transfers) > 1:
                message = _(
                    "Se crearon %(count)s solicitudes de transferencia desde bodega "
                    "principal. Apruébelas para mover los componentes a producción.",
                    count=len(transfers),
                )
        else:
            title = _("Transferencias generadas")
            message = _(
                "Se crearon %(count)s solicitudes de transferencia desde bodega "
                "principal en las órdenes seleccionadas.",
                count=len(transfers),
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "links": links,
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                },
            },
        }

    def _hn_notify_pending_material_pickings(self):
        Transfer = self.env["hn.production.material.transfer"]
        pickings = self.env["stock.picking"]
        for production in self:
            transfers = Transfer.search(
                [
                    ("production_id", "=", production.id),
                    ("state", "=", "approved"),
                    ("picking_id", "!=", False),
                ]
            )
            pickings |= transfers.picking_id.filtered(
                lambda p: p.state not in ("done", "cancel")
            )
        pickings = pickings.exists()
        if not pickings:
            return False
        links = [
            {
                "label": picking.display_name,
                "url": "/odoo/stock.picking/%s" % picking.id,
            }
            for picking in pickings
        ]
        if len(pickings) == 1:
            message = _(
                "Hay material aprobado en %(picking)s que aún no llega a materia prima. "
                "Valide el picking (Marcar hecho) y vuelva a comprobar disponibilidad.",
                picking=pickings.display_name,
            )
        else:
            message = _(
                "Hay %(count)s pickings con material aprobado que aún no llega a materia "
                "prima. Valídelos (Marcar hecho) y vuelva a comprobar disponibilidad.",
                count=len(pickings),
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pickings pendientes de validar"),
                "message": message,
                "links": links,
                "type": "warning",
                "sticky": True,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                },
            },
        }

    def action_generate_material_transfer(self):
        """Genera una solicitud parcial con los faltantes transferibles desde bodega principal."""
        self.ensure_one()
        if self.state == "cancel":
            raise UserError(_("No se puede generar transferencia en una OP cancelada."))
        if self.state == "done":
            raise UserError(_("La orden ya está terminada."))
        Transfer = self.env["hn.production.material.transfer"]
        transfer = Transfer.create_from_production(self)
        if transfer:
            return self.action_view_material_transfers(transfer=transfer)

        analysis = Transfer._get_production_shortage_analysis(self)
        issues = [item for item in analysis if item["status"] != "ok"]
        if not issues:
            raise UserError(
                _(
                    "No hay componentes pendientes de transferencia para esta orden."
                )
            )
        details = []
        for item in issues:
            details.append("• %s: %s" % (item["product"].display_name, item["reason"]))
        raise UserError(
            _(
                "No se generó transferencia. Revise los faltantes:\n%s"
            )
            % "\n".join(details)
        )

    def _update_raw_moves(self, factor):
        self.ensure_one()
        update_info = []
        for move in self.move_raw_ids.filtered(
            lambda item: item.state not in ("done", "cancel") and not item.hn_pack_id
        ):
            old_qty = move.product_uom_qty
            new_qty = move.product_uom.round(old_qty * factor, rounding_method="UP")
            if new_qty > 0:
                move.write({"product_uom_qty": new_qty})
                update_info.append((move, old_qty, new_qty))
            if move.reference_ids != self.reference_ids:
                move.reference_ids = self.reference_ids.ids
        return update_info

    @api.depends(
        "hn_pack_ids.move_ids",
        "hn_pack_ids.move_ids.state",
        "hn_pack_ids.move_ids.product_uom_qty",
    )
    def _compute_hn_pack_move_ids(self):
        for production in self:
            production.hn_pack_move_ids = production.hn_pack_ids.move_ids.filtered(
                lambda move: move.state != "cancel"
            )

    @api.depends(
        "hn_pack_ids.total_cost",
        "hn_pack_ids.move_ids.product_uom_qty",
        "hn_pack_ids.move_ids.quantity",
        "hn_pack_ids.move_ids.state",
        "hn_pack_ids.move_ids.product_id",
    )
    def _compute_hn_pack_cost_total(self):
        for production in self:
            production.hn_pack_cost_total = sum(production.hn_pack_ids.mapped("total_cost"))

    def action_view_material_transfers(self, transfer=False):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Transferencias de materiales"),
            "res_model": "hn.production.material.transfer",
            "view_mode": "list,form",
            "domain": [("production_id", "=", self.id)],
            "context": {"default_production_id": self.id},
        }
        transfer = transfer or self.material_transfer_ids[:1]
        if transfer and len(transfer) == 1:
            action["view_mode"] = "form"
            action["res_id"] = transfer.id
        return action
