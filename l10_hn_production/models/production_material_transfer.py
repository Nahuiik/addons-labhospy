# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class HnProductionMaterialTransfer(models.Model):
    _name = "hn.production.material.transfer"
    _description = "Transferencia de materiales a producción"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Referencia",
        default="/",
        copy=False,
        readonly=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("pending_approval", "Pendiente aprobación"),
            ("approved", "Aprobado"),
            ("done", "Hecho"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="pending_approval",
        copy=False,
        tracking=True,
        readonly=True,
    )
    production_id = fields.Many2one(
        "mrp.production",
        string="Orden de producción",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Bodega A",
        required=True,
        readonly=True,
        check_company=True,
    )
    dest_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Bodega de producción",
        required=True,
        readonly=True,
        check_company=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Ubicación origen",
        required=True,
        readonly=True,
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Ubicación destino",
        required=True,
        readonly=True,
    )
    picking_id = fields.Many2one(
        "stock.picking",
        string="Transferencia de inventario",
        readonly=True,
        copy=False,
    )
    line_ids = fields.One2many(
        "hn.production.material.transfer.line",
        "transfer_id",
        string="Líneas",
    )
    submitted_by = fields.Many2one(
        "res.users",
        string="Solicitado por",
        readonly=True,
        copy=False,
    )
    submitted_date = fields.Datetime(
        string="Fecha solicitud",
        readonly=True,
        copy=False,
    )
    approved_by = fields.Many2one(
        "res.users",
        string="Aprobado por",
        readonly=True,
        copy=False,
        tracking=True,
    )
    approved_date = fields.Datetime(
        string="Fecha aprobación",
        readonly=True,
        copy=False,
    )
    rejected_by = fields.Many2one(
        "res.users",
        string="Rechazado por",
        readonly=True,
        copy=False,
    )
    rejected_date = fields.Datetime(
        string="Fecha rechazo",
        readonly=True,
        copy=False,
    )
    rejection_reason = fields.Text(
        string="Motivo de rechazo",
        readonly=True,
        copy=False,
    )
    is_current_user_submitter = fields.Boolean(
        compute="_compute_is_current_user_submitter",
    )
    can_user_approve = fields.Boolean(
        compute="_compute_can_user_approve",
    )
    can_edit_transfer_lines = fields.Boolean(
        compute="_compute_can_edit_transfer_lines",
    )

    _EDITABLE_TRANSFER_LINE_FIELDS = frozenset({"lot_id", "qty_to_transfer"})

    @api.depends("submitted_by")
    def _compute_is_current_user_submitter(self):
        uid = self.env.user.id
        for transfer in self:
            transfer.is_current_user_submitter = (
                bool(transfer.submitted_by) and transfer.submitted_by.id == uid
            )

    @api.depends(
        "state",
        "submitted_by",
        "company_id.hn_production_allow_self_approval",
    )
    def _compute_can_user_approve(self):
        uid = self.env.user.id
        is_approver = self.env.user.has_group(
            "l10_hn_production.group_production_material_approver"
        )
        for transfer in self:
            if transfer.state != "pending_approval" or not is_approver:
                transfer.can_user_approve = False
                continue
            is_submitter = (
                bool(transfer.submitted_by) and transfer.submitted_by.id == uid
            )
            allow_self = transfer.company_id.hn_production_allow_self_approval
            transfer.can_user_approve = not is_submitter or allow_self

    @api.depends("state", "submitted_by")
    def _compute_can_edit_transfer_lines(self):
        approver_group = "l10_hn_production.group_production_material_approver"
        for transfer in self:
            if transfer.state != "pending_approval":
                transfer.can_edit_transfer_lines = False
                continue
            user = self.env.user
            if user.has_group(approver_group):
                transfer.can_edit_transfer_lines = True
            else:
                transfer.can_edit_transfer_lines = (
                    transfer.submitted_by == user
                )

    def _user_can_edit_transfer_lines(self):
        self.ensure_one()
        return self.can_edit_transfer_lines

    def write(self, vals):
        if not self:
            return super().write(vals)
        if self.env.su or self.env.context.get("hn_production_transfer_auto_write"):
            return super().write(vals)
        approver_group = "l10_hn_production.group_production_material_approver"
        if self.env.user.has_group(approver_group):
            return super().write(vals)
        if vals:
            raise UserError(
                _(
                    "No tiene permiso para modificar la solicitud. "
                    "Ajuste lotes y cantidades en la pestaña Componentes."
                )
            )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "hn.production.material.transfer"
                    )
                    or "/"
                )
        transfers = super().create(vals_list)
        transfers._schedule_approver_activities()
        return transfers

    def _product_qty_available_at_location(self, product, location, company):
        """Cantidad libre (no reservada) en la ubicación destino."""
        product = product.with_company(company)
        quants = self.env["stock.quant"].sudo()._gather(
            product,
            location,
            strict=False,
        )
        available = 0.0
        for quant in quants:
            available += quant.quantity - quant.reserved_quantity
        return max(available, 0.0)

    @api.model
    def _lot_expiration(self, lot):
        if not lot:
            return False
        for attr in ("expiration_date", "use_date", "removal_date"):
            value = getattr(lot, attr, False)
            if value:
                return value
        return False

    @api.model
    def _allocate_source_lots(self, product, location, company, qty_needed):
        """Propone lotes/series desde la Bodega A (FEFO) para la cantidad pendiente."""
        rounding = product.uom_id.rounding
        if float_is_zero(qty_needed, precision_rounding=rounding):
            return []

        if product.tracking == "none":
            return [{"lot_id": False, "qty": qty_needed}]

        Quant = self.env["stock.quant"].sudo()
        quants = Quant._gather(product.with_company(company), location, strict=False)
        lot_buckets = {}
        for quant in quants:
            free = quant.quantity - quant.reserved_quantity
            if float_is_zero(free, precision_rounding=rounding):
                continue
            lot = quant.lot_id
            if not lot:
                continue
            bucket = lot_buckets.setdefault(
                lot.id,
                {"lot": lot, "free": 0.0, "expiration": self._lot_expiration(lot)},
            )
            bucket["free"] += free

        ordered = sorted(
            lot_buckets.values(),
            key=lambda item: (item["expiration"] or fields.Datetime.max, item["lot"].id),
        )

        allocations = []
        remaining = qty_needed

        if product.tracking == "serial":
            for bucket in ordered:
                while (
                    not float_is_zero(remaining, precision_rounding=rounding)
                    and bucket["free"] >= 1.0
                ):
                    allocations.append({"lot_id": bucket["lot"].id, "qty": 1.0})
                    bucket["free"] -= 1.0
                    remaining -= 1.0
        else:
            for bucket in ordered:
                if float_is_zero(remaining, precision_rounding=rounding):
                    break
                take = min(remaining, bucket["free"])
                if float_is_zero(take, precision_rounding=rounding):
                    continue
                allocations.append({"lot_id": bucket["lot"].id, "qty": take})
                remaining -= take

        if not float_is_zero(remaining, precision_rounding=rounding):
            allocations.append({"lot_id": False, "qty": remaining})

        return allocations

    @api.model
    def _transferable_raw_moves(self, production):
        """Componentes físicos de la OP (almacenables y consumibles)."""
        return production.move_raw_ids.filtered(
            lambda m: m.state != "cancel"
            and m.product_id.type in ("product", "consu")
        )

    @api.model
    def _move_covered_qty(self, move):
        """Cantidad del componente ya reservada o consumida para la OP."""
        product = move.product_id
        uom = move.product_uom or product.uom_id
        if move.state == "done":
            qty = move.quantity
        elif move.state in ("assigned", "partially_available"):
            qty = move.quantity
        else:
            qty = 0.0
        return uom._compute_quantity(qty, product.uom_id)

    @api.model
    def _production_required_qty_by_product(self, production):
        """Retorna {product: qty_required, move_raw_id} agregado por producto."""
        buckets = {}
        for move in self._transferable_raw_moves(production):
            product = move.product_id
            uom = move.product_uom or product.uom_id
            qty_required = uom._compute_quantity(
                move.product_uom_qty,
                product.uom_id,
            )
            bucket = buckets.setdefault(
                product.id,
                {
                    "product": product,
                    "qty_required": 0.0,
                    "qty_covered": 0.0,
                    "move_raw_id": move.id,
                },
            )
            bucket["qty_required"] += qty_required
            bucket["qty_covered"] += self._move_covered_qty(move)
        return buckets

    @api.model
    def _get_requested_transfer_qty_by_product(self, production):
        """Cantidad ya solicitada en transferencias activas (aún no recibida)."""
        requested = defaultdict(float)
        transfers = self.search(
            [
                ("production_id", "=", production.id),
                ("state", "in", ("pending_approval", "approved")),
            ]
        )
        for transfer in transfers:
            for line in transfer.line_ids:
                requested[line.product_id] += line.qty_to_transfer
        return requested

    @api.model
    def _get_transfer_status_by_product(self, production):
        """Desglose por producto de transferencias pendientes de aprobar o validar."""
        status = defaultdict(
            lambda: {
                "pending_approval": 0.0,
                "pending_picking": 0.0,
                "pickings": set(),
                "transfers_pending": set(),
            }
        )
        transfers = self.search(
            [
                ("production_id", "=", production.id),
                ("state", "in", ("pending_approval", "approved")),
            ]
        )
        for transfer in transfers:
            for line in transfer.line_ids:
                bucket = status[line.product_id]
                if transfer.state == "pending_approval":
                    bucket["pending_approval"] += line.qty_to_transfer
                    bucket["transfers_pending"].add(transfer.display_name)
                elif (
                    transfer.picking_id
                    and transfer.picking_id.state not in ("done", "cancel")
                ):
                    bucket["pending_picking"] += line.qty_to_transfer
                    bucket["pickings"].add(transfer.picking_id.display_name)
        return status

    @api.model
    def _production_transfer_need_by_product(
        self, production, dest_location, company
    ):
        """Retorna {product: qty_to_transfer} pendiente hacia la bodega destino."""
        del dest_location  # compatibilidad; la cobertura se calcula por reservas de la OP
        requested = self._get_requested_transfer_qty_by_product(production)
        result = {}
        for data in self._production_required_qty_by_product(production).values():
            product = data["product"]
            qty_still_needed = max(
                data["qty_required"] - data["qty_covered"], 0.0
            )
            qty_to_transfer = max(
                qty_still_needed - requested.get(product, 0.0), 0.0
            )
            if not float_is_zero(
                qty_to_transfer, precision_rounding=product.uom_id.rounding
            ):
                result[product] = qty_to_transfer
        return result

    @api.model
    def _get_production_shortage_analysis(self, production):
        """Analiza faltantes de componentes para transferencia y reserva."""
        company = production.company_id
        source_wh = company.hn_production_source_warehouse_id
        dest_wh = company.hn_production_dest_warehouse_id
        if not source_wh or not dest_wh:
            return []

        source_location = source_wh.lot_stock_id
        dest_location = dest_wh.lot_stock_id
        requested = self._get_requested_transfer_qty_by_product(production)
        transfer_status = self._get_transfer_status_by_product(production)
        analysis = []

        for data in self._production_required_qty_by_product(production).values():
            product = data["product"]
            rounding = product.uom_id.rounding
            qty_required = data["qty_required"]
            qty_covered = data["qty_covered"]
            qty_still_needed = max(qty_required - qty_covered, 0.0)
            qty_requested = requested.get(product, 0.0)
            qty_transferable = max(qty_still_needed - qty_requested, 0.0)
            qty_bp = self._product_qty_available_at_location(
                product, source_location, company
            )
            qty_dest_free = self._product_qty_available_at_location(
                product, dest_location, company
            )
            product_transfer = transfer_status.get(product, {})
            pending_picking = product_transfer.get("pending_picking", 0.0)
            pending_approval = product_transfer.get("pending_approval", 0.0)
            pickings = ", ".join(sorted(product_transfer.get("pickings", ())))
            transfers_pending = ", ".join(
                sorted(product_transfer.get("transfers_pending", ()))
            )

            if float_is_zero(qty_still_needed, precision_rounding=rounding):
                status = "ok"
                reason = _("Disponible para la orden.")
            elif not float_is_zero(pending_picking, precision_rounding=rounding):
                status = "pending_picking"
                if float_compare(
                    pending_picking, qty_still_needed, precision_rounding=rounding
                ) >= 0:
                    reason = _(
                        "Transferencia aprobada (%(qty)s). Valide el picking %(pickings)s "
                        "para recibir el material en materia prima.",
                        qty=pending_picking,
                        pickings=pickings,
                    )
                else:
                    reason = _(
                        "Faltan %(need)s; hay %(qty)s aprobados en %(pickings)s "
                        "pendientes de validar (Marcar hecho).",
                        need=qty_still_needed,
                        qty=pending_picking,
                        pickings=pickings,
                    )
            elif not float_is_zero(pending_approval, precision_rounding=rounding):
                status = "pending_approval"
                if float_compare(
                    pending_approval, qty_still_needed, precision_rounding=rounding
                ) >= 0:
                    reason = _(
                        "Solicitud %(transfers)s pendiente de aprobación (%(qty)s).",
                        transfers=transfers_pending,
                        qty=pending_approval,
                    )
                else:
                    reason = _(
                        "Faltan %(need)s; hay %(qty)s en %(transfers)s pendientes de aprobación.",
                        need=qty_still_needed,
                        qty=pending_approval,
                        transfers=transfers_pending,
                    )
            elif float_compare(qty_requested, qty_still_needed, precision_rounding=rounding) >= 0:
                status = "pending_transfer"
                reason = _(
                    "Transferencia solicitada (%(qty)s); pendiente aprobación o recepción.",
                    qty=qty_requested,
                )
            elif not float_is_zero(qty_transferable, precision_rounding=rounding) and not float_is_zero(
                qty_bp, precision_rounding=rounding
            ):
                status = "transferable"
                reason = _(
                    "Faltan %(need)s; hay %(bp)s en bodega principal disponibles para transferir.",
                    need=qty_transferable,
                    bp=min(qty_transferable, qty_bp),
                )
            elif float_is_zero(qty_bp, precision_rounding=rounding):
                status = "no_bp_stock"
                reason = _(
                    "Faltan %(need)s en materia prima y no hay stock libre en bodega principal.",
                    need=qty_still_needed,
                )
            else:
                status = "partial"
                reason = _(
                    "Faltan %(need)s; solo hay %(bp)s libres en bodega principal.",
                    need=qty_still_needed,
                    bp=qty_bp,
                )

            analysis.append(
                {
                    "product": product,
                    "qty_required": qty_required,
                    "qty_covered": qty_covered,
                    "qty_still_needed": qty_still_needed,
                    "qty_requested": qty_requested,
                    "qty_transferable": min(qty_transferable, qty_bp)
                    if status == "transferable"
                    else qty_transferable,
                    "qty_bp": qty_bp,
                    "qty_dest_free": qty_dest_free,
                    "status": status,
                    "reason": reason,
                }
            )
        return analysis

    @api.model
    def _prepare_lines_from_production(
        self, production, source_location, dest_location
    ):
        lines = []
        company = production.company_id
        needs = self._production_transfer_need_by_product(
            production, dest_location, company
        )
        required_data = self._production_required_qty_by_product(production)

        for product, qty_to_transfer in needs.items():
            data = required_data[product.id]
            product = data["product"]
            qty_required = data["qty_required"]
            qty_covered = data["qty_covered"]
            qty_available = max(qty_required - qty_covered, 0.0)

            qty_source = self._product_qty_available_at_location(
                product,
                source_location,
                company,
            )
            if float_is_zero(qty_source, precision_rounding=product.uom_id.rounding):
                continue

            qty_to_transfer = min(qty_to_transfer, qty_source)

            allocations = self._allocate_source_lots(
                product,
                source_location,
                company,
                qty_to_transfer,
            )
            if not allocations:
                allocations = [{"lot_id": False, "qty": qty_to_transfer}]

            qty_available_dest = self._product_qty_available_at_location(
                product,
                dest_location,
                company,
            )
            for alloc in allocations:
                lines.append(
                    {
                        "product_id": product.id,
                        "product_uom_id": product.uom_id.id,
                        "qty_required": qty_required,
                        "qty_available_dest": qty_available_dest,
                        "qty_to_transfer": alloc["qty"],
                        "lot_id": alloc.get("lot_id") or False,
                        "move_raw_id": data["move_raw_id"],
                    }
                )
        return lines

    @api.model
    def create_from_production(self, production):
        production.ensure_one()
        if production.state in ("cancel", "done"):
            return self.env["hn.production.material.transfer"]

        company = production.company_id
        source_wh = company.hn_production_source_warehouse_id
        dest_wh = company.hn_production_dest_warehouse_id
        if not source_wh or not dest_wh:
            production.message_post(
                body=_(
                    "No se generó transferencia de materiales: configure la "
                    "Bodega A y la Bodega de producción en la compañía "
                    "(Fabricación → Configuración → Bodegas de producción)."
                ),
                subtype_xmlid="mail.mt_note",
            )
            return self.env["hn.production.material.transfer"]

        if not source_wh.lot_stock_id or not dest_wh.lot_stock_id:
            raise UserError(
                _(
                    "Los almacenes configurados deben tener ubicación de existencias."
                )
            )

        line_vals = self._prepare_lines_from_production(
            production,
            source_wh.lot_stock_id,
            dest_wh.lot_stock_id,
        )
        needs = self._production_transfer_need_by_product(
            production, dest_wh.lot_stock_id, company
        )
        missing_source = []
        for product in needs:
            qty_source = self._product_qty_available_at_location(
                product, source_wh.lot_stock_id, company
            )
            if float_is_zero(
                qty_source, precision_rounding=product.uom_id.rounding
            ):
                missing_source.append(product.display_name)

        if not line_vals:
            return self.env["hn.production.material.transfer"]

        if missing_source:
            production.message_post(
                body=_(
                    "Transferencia parcial: estos componentes faltan en «%(dest)s» "
                    "pero no tienen stock libre en «%(src)s»: %(products)s.",
                    dest=dest_wh.display_name,
                    src=source_wh.display_name,
                    products=", ".join(missing_source),
                ),
                subtype_xmlid="mail.mt_note",
            )

        transfer = self.create(
            {
                "production_id": production.id,
                "company_id": company.id,
                "source_warehouse_id": source_wh.id,
                "dest_warehouse_id": dest_wh.id,
                "location_id": source_wh.lot_stock_id.id,
                "location_dest_id": dest_wh.lot_stock_id.id,
                "submitted_by": self.env.uid,
                "submitted_date": fields.Datetime.now(),
                "line_ids": [Command.create(vals) for vals in line_vals],
            }
        )
        transfer.message_post(
            body=_(
                "Solicitud de transferencia creada al confirmar la orden de producción. "
                "Pendiente de aprobación."
            ),
            subtype_xmlid="mail.mt_note",
        )
        missing_lots = transfer.line_ids.filtered(
            lambda l: l.product_id.tracking in ("lot", "serial") and not l.lot_id
        )
        if missing_lots:
            transfer.message_post(
                body=_(
                    "Algunos componentes con trazabilidad no pudieron asignarse "
                    "automáticamente a lote/serie. El aprobador debe completarlos "
                    "antes de aprobar."
                ),
                subtype_xmlid="mail.mt_note",
            )
        return transfer

    def _schedule_approver_activities(self):
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        if not activity_type:
            return
        group = self.env.ref(
            "l10_hn_production.group_production_material_approver",
            raise_if_not_found=False,
        )
        if not group:
            return
        for transfer in self.filtered(lambda t: t.state == "pending_approval"):
            approvers = group.user_ids.filtered(
                lambda user: user.id != (transfer.submitted_by.id or 0)
            )
            summary = _("Aprobar transferencia a producción")
            note = _(
                "Solicitud %(transfer)s de la orden de producción %(mo)s.",
                transfer=transfer.name,
                mo=transfer.production_id.display_name,
            )
            for user in approvers:
                existing = transfer.activity_ids.filtered(
                    lambda act: act.user_id == user
                    and act.activity_type_id == activity_type
                    and act.state != "done"
                )
                if existing:
                    continue
                transfer.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    summary=summary,
                    note=note,
                )

    def _close_approver_activities(self, feedback):
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        for transfer in self:
            activities = transfer.activity_ids.filtered(
                lambda act: not activity_type
                or act.activity_type_id == activity_type
            )
            if activities:
                activities.action_feedback(feedback=feedback)

    def _check_approver_access(self):
        if not self.env.user.has_group(
            "l10_hn_production.group_production_material_approver"
        ):
            raise UserError(
                _(
                    "No tiene permisos para aprobar o rechazar transferencias "
                    "de materiales a producción."
                )
            )

    def _check_not_self_approval(self):
        for transfer in self:
            if (
                transfer.submitted_by
                and transfer.submitted_by == self.env.user
                and not transfer.company_id.hn_production_allow_self_approval
            ):
                raise UserError(
                    _(
                        "No puede aprobar ni rechazar una solicitud que usted mismo generó. "
                        "Otra persona con rol de responsable debe aprobarla, o active "
                        "«Permitir autoaprobación» en Ajustes → Fabricación."
                    )
                )

    def _get_internal_picking_type(self):
        self.ensure_one()
        picking_type = self.source_warehouse_id.int_type_id
        if not picking_type:
            raise UserError(
                _(
                    "El almacén «%s» no tiene tipo de operación interno configurado."
                )
                % self.source_warehouse_id.display_name
            )
        return picking_type

    def _validate_lines_for_approval(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("La solicitud no tiene líneas de productos."))

        uom_dp = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        product_qty = {}
        for line in self.line_ids:
            if float_is_zero(
                line.qty_to_transfer,
                precision_rounding=line.product_uom_id.rounding,
            ):
                raise UserError(
                    _(
                        "La cantidad a transferir debe ser positiva en %(product)s.",
                        product=line.product_id.display_name,
                    )
                )
            line._check_lot_requirements()
            if line.product_id.tracking in ("lot", "serial") and line.lot_id:
                free = self.env["stock.quant"]._get_available_quantity(
                    line.product_id,
                    self.location_id,
                    lot_id=line.lot_id,
                    strict=True,
                )
                if float_compare(
                    line.qty_to_transfer, free, precision_digits=uom_dp
                ) > 0:
                    raise UserError(
                        _(
                            "No hay cantidad suficiente del lote/serie «%(lot)s» "
                            "en origen para «%(product)s»: disponible %(avail)s, "
                            "solicitado %(need)s.",
                            lot=line.lot_id.display_name,
                            product=line.product_id.display_name,
                            avail=free,
                            need=line.qty_to_transfer,
                        )
                    )

            pid = line.product_id.id
            product_qty[pid] = product_qty.get(pid, 0.0) + line.qty_to_transfer

        other_requested = defaultdict(float)
        other_transfers = self.search(
            [
                ("production_id", "=", self.production_id.id),
                ("state", "in", ("pending_approval", "approved")),
                ("id", "!=", self.id),
            ]
        )
        for transfer in other_transfers:
            for line in transfer.line_ids:
                other_requested[line.product_id] += line.qty_to_transfer

        required_data = self._production_required_qty_by_product(self.production_id)
        for product_id, qty_lines in product_qty.items():
            data = required_data.get(product_id)
            if not data:
                continue
            product = data["product"]
            qty_still_needed = max(
                data["qty_required"] - data["qty_covered"], 0.0
            )
            qty_expected = max(
                qty_still_needed - other_requested.get(product, 0.0), 0.0
            )
            if float_compare(
                qty_lines, qty_expected, precision_digits=uom_dp
            ) > 0:
                raise UserError(
                    _(
                        "La suma transferida de «%(product)s» (%(actual)s) supera "
                        "la cantidad pendiente (%(expected)s). Revise lotes y cantidades.",
                        product=product.display_name,
                        actual=qty_lines,
                        expected=qty_expected,
                    )
                )
            if float_compare(qty_lines, qty_expected, precision_digits=uom_dp) < 0:
                raise UserError(
                    _(
                        "La suma transferida de «%(product)s» (%(actual)s) no coincide "
                        "con la cantidad pendiente (%(expected)s). Revise lotes y cantidades.",
                        product=product.display_name,
                        actual=qty_lines,
                        expected=qty_expected,
                    )
                )

    def _command_create_move_for_line(self, line):
        self.ensure_one()
        vals = {
            "product_id": line.product_id.id,
            "product_uom_qty": line.qty_to_transfer,
            "product_uom": line.product_uom_id.id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
            "company_id": self.company_id.id,
            "origin": self.name,
        }
        if line.lot_id:
            vals["move_line_ids"] = [
                Command.create(
                    {
                        "product_id": line.product_id.id,
                        "product_uom_id": line.product_uom_id.id,
                        "location_id": self.location_id.id,
                        "location_dest_id": self.location_dest_id.id,
                        "quantity": line.qty_to_transfer,
                        "lot_id": line.lot_id.id,
                    }
                )
            ]
        return Command.create(vals)

    def _prepare_picking_vals(self):
        self.ensure_one()
        picking_type = self._get_internal_picking_type()
        move_commands = []
        for line in self.line_ids.filtered(
            lambda l: not float_is_zero(
                l.qty_to_transfer,
                precision_rounding=l.product_uom_id.rounding,
            )
        ):
            move_commands.append(self._command_create_move_for_line(line))
        if not move_commands:
            raise UserError(_("No hay cantidades pendientes por transferir."))

        vals = {
            "picking_type_id": picking_type.id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
            "origin": "%s / %s"
            % (self.production_id.name, self.name),
            "company_id": self.company_id.id,
            "move_ids": move_commands,
        }
        if "branch_id" in self.env["stock.picking"]._fields:
            branch = getattr(self.source_warehouse_id, "branch_id", False)
            if branch:
                vals["branch_id"] = branch.id
        if "hn_production_material_transfer_id" in self.env["stock.picking"]._fields:
            vals["hn_production_material_transfer_id"] = self.id
        return vals

    def action_approve(self):
        self._check_approver_access()
        self._check_not_self_approval()
        pickings = self.env["stock.picking"]
        for transfer in self:
            if transfer.state != "pending_approval":
                raise UserError(_("Solo se pueden aprobar solicitudes pendientes."))
            if transfer.picking_id:
                raise UserError(_("Esta solicitud ya tiene una transferencia vinculada."))

            transfer._validate_lines_for_approval()
            picking = self.env["stock.picking"].create(
                transfer._prepare_picking_vals()
            )
            picking.action_confirm()
            if hasattr(picking, "action_assign"):
                picking.action_assign()
            pickings |= picking
            transfer.write(
                {
                    "picking_id": picking.id,
                    "state": "approved",
                    "approved_by": self.env.uid,
                    "approved_date": fields.Datetime.now(),
                }
            )
            transfer._close_approver_activities(_("Transferencia aprobada."))
            transfer.message_post(
                body=_(
                    "Transferencia aprobada. Picking generado: %s"
                )
                % picking.display_name,
                subtype_xmlid="mail.mt_note",
            )
            transfer.production_id.message_post(
                body=_(
                    "Transferencia de materiales aprobada (%s). Picking: %s. "
                    "Debe validarlo (Marcar hecho) para que el stock llegue a materia prima."
                )
                % (transfer.name, picking.display_name),
                subtype_xmlid="mail.mt_note",
            )
        if len(self) == 1 and len(pickings) == 1:
            picking = pickings
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Transferencia aprobada"),
                    "message": _(
                        "Se generó el picking %(picking)s. Debe validarlo (Marcar hecho) "
                        "para que el stock llegue a materia prima y la orden pueda reservarlo.",
                        picking=picking.display_name,
                    ),
                    "links": [
                        {
                            "label": picking.display_name,
                            "url": "/odoo/stock.picking/%s" % picking.id,
                        }
                    ],
                    "type": "warning",
                    "sticky": True,
                    "next": {
                        "type": "ir.actions.act_window",
                        "res_model": "stock.picking",
                        "res_id": picking.id,
                        "views": [(False, "form")],
                        "target": "current",
                    },
                },
            }
        return True

    def action_reject(self):
        self._check_approver_access()
        self._check_not_self_approval()
        self.ensure_one()
        if self.state != "pending_approval":
            raise UserError(_("Solo se pueden rechazar solicitudes pendientes."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar transferencia"),
            "res_model": "hn.production.material.transfer.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_transfer_id": self.id},
        }

    def _apply_rejection(self, reason):
        for transfer in self.filtered(lambda t: t.state == "pending_approval"):
            transfer.write(
                {
                    "state": "cancelled",
                    "rejected_by": self.env.uid,
                    "rejected_date": fields.Datetime.now(),
                    "rejection_reason": reason,
                }
            )
            transfer._close_approver_activities(_("Transferencia rechazada."))
            transfer.message_post(
                body=_("Transferencia rechazada. Motivo: %s") % reason,
                subtype_xmlid="mail.mt_note",
            )
            transfer.production_id.message_post(
                body=_(
                    "Transferencia de materiales rechazada (%s). Motivo: %s"
                )
                % (transfer.name, reason),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def action_cancel(self):
        self._check_approver_access()
        for transfer in self:
            if transfer.state == "done":
                raise UserError(_("No se puede cancelar una transferencia ya completada."))
            if transfer.picking_id and transfer.picking_id.state not in (
                "cancel",
                "done",
            ):
                transfer.picking_id.action_cancel()
            transfer.state = "cancelled"
            transfer._close_approver_activities(_("Transferencia cancelada."))
        return True

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No hay transferencia de inventario vinculada."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Transferencia de inventario"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.picking_id.id,
        }


class HnProductionMaterialTransferLine(models.Model):
    _name = "hn.production.material.transfer.line"
    _description = "Línea transferencia materiales producción"

    transfer_id = fields.Many2one(
        "hn.production.material.transfer",
        string="Transferencia",
        required=True,
        ondelete="cascade",
        index=True,
    )
    transfer_state = fields.Selection(
        related="transfer_id.state",
        readonly=True,
    )
    can_edit_lines = fields.Boolean(
        related="transfer_id.can_edit_transfer_lines",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        readonly=True,
    )
    product_tracking = fields.Selection(
        related="product_id.tracking",
        string="Trazado",
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="UdM",
        required=True,
        readonly=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lote / Serie",
        check_company=True,
        domain="[('product_id', '=', product_id), ('id', 'in', allowed_lot_ids), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    allowed_lot_ids = fields.Many2many(
        "stock.lot",
        string="Lotes disponibles en origen",
        compute="_compute_allowed_lot_ids",
        help="Lotes/series con existencia libre en la bodega origen.",
    )
    qty_required = fields.Float(
        string="Cantidad requerida",
        digits="Product Unit of Measure",
        readonly=True,
        help="Cantidad necesaria según la orden de producción.",
    )
    qty_available_dest = fields.Float(
        string="Disponible en producción",
        digits="Product Unit of Measure",
        readonly=True,
        help="Inventario libre en la bodega de producción al generar la solicitud.",
    )
    qty_to_transfer = fields.Float(
        string="Cantidad a transferir",
        digits="Product Unit of Measure",
        help="Cantidad a mover en este lote o línea.",
    )
    qty_available_origin = fields.Float(
        string="Disponible en origen",
        compute="_compute_qty_available_origin",
        digits="Product Unit of Measure",
    )
    move_raw_id = fields.Many2one(
        "stock.move",
        string="Movimiento componente",
        readonly=True,
        ondelete="set null",
    )
    company_id = fields.Many2one(
        related="transfer_id.company_id",
        store=True,
        readonly=True,
    )

    @api.depends("product_id", "transfer_id.location_id", "transfer_id.state")
    def _compute_allowed_lot_ids(self):
        Quant = self.env["stock.quant"].sudo()
        for line in self:
            lots = self.env["stock.lot"]
            if (
                line.product_id
                and line.product_id.tracking != "none"
                and line.transfer_id.location_id
            ):
                quants = Quant.search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("location_id", "child_of", line.transfer_id.location_id.id),
                        ("lot_id", "!=", False),
                    ]
                )
                for quant in quants:
                    if quant.quantity - quant.reserved_quantity > 0:
                        lots |= quant.lot_id
            line.allowed_lot_ids = lots

    def write(self, vals):
        if not self.env.su:
            illegal = set(vals) - HnProductionMaterialTransfer._EDITABLE_TRANSFER_LINE_FIELDS
            for line in self:
                transfer = line.transfer_id
                if not transfer._user_can_edit_transfer_lines():
                    raise UserError(
                        _(
                            "No tiene permiso para modificar líneas de la "
                            "solicitud %(name)s.",
                            name=transfer.name,
                        )
                    )
                if illegal:
                    raise UserError(
                        _(
                            "Solo puede modificar lote/serie y cantidad a transferir."
                        )
                    )
        return super().write(vals)

    @api.onchange("lot_id")
    def _onchange_lot_id_serial_qty(self):
        if (
            self.product_id
            and self.product_id.tracking == "serial"
            and self.lot_id
        ):
            self.qty_to_transfer = 1.0

    @api.depends(
        "product_id",
        "lot_id",
        "transfer_id.location_id",
    )
    def _compute_qty_available_origin(self):
        for line in self:
            if (
                not line.product_id
                or not line.transfer_id
                or not line.transfer_id.location_id
            ):
                line.qty_available_origin = 0.0
                continue
            if line.product_id.tracking in ("lot", "serial") and line.lot_id:
                line.qty_available_origin = self.env["stock.quant"]._get_available_quantity(
                    line.product_id,
                    line.transfer_id.location_id,
                    lot_id=line.lot_id,
                    strict=True,
                )
            else:
                line.qty_available_origin = line.product_id.with_context(
                    location=line.transfer_id.location_id.id
                ).free_qty

    def _check_lot_requirements(self, require_lot=True):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for line in self:
            if not line.product_id:
                continue
            if line.product_id.tracking == "none" and line.lot_id:
                raise ValidationError(
                    _(
                        "No indique lote/serie en %(product)s: el producto no usa trazado.",
                        product=line.product_id.display_name,
                    )
                )
            if (
                require_lot
                and line.product_id.tracking in ("lot", "serial")
                and not line.lot_id
            ):
                raise ValidationError(
                    _(
                        "Debe indicar lote/serie en %(product)s antes de aprobar.",
                        product=line.product_id.display_name,
                    )
                )
            if line.product_id.tracking == "serial" and not float_is_zero(
                line.qty_to_transfer, precision_digits=precision
            ) and float_compare(
                line.qty_to_transfer, 1.0, precision_digits=precision
            ) != 0:
                raise ValidationError(
                    _(
                        "Con trazado por serie, la cantidad en cada línea debe ser 1 "
                        "para %(product)s.",
                        product=line.product_id.display_name,
                    )
                )
            if line.lot_id and line.lot_id.product_id != line.product_id:
                raise ValidationError(
                    _(
                        "El lote «%(lot)s» no corresponde al producto «%(product)s».",
                        lot=line.lot_id.display_name,
                        product=line.product_id.display_name,
                    )
                )

    @api.constrains("lot_id", "product_id", "qty_to_transfer", "transfer_id")
    def _check_line_editable_constraints(self):
        for line in self.filtered(
            lambda l: l.transfer_id.state == "pending_approval"
        ):
            line._check_lot_requirements(require_lot=False)
