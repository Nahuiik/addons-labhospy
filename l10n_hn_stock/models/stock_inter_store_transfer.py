# -*- coding: utf-8 -*-
# Part of l10n_hn_stock. See LICENSE file for full copyright and licensing details.

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class StockInterStoreTransfer(models.Model):
    """Traslado entre tiendas (A → tránsito → B).

    Por qué puede cambiar el «costo» en la ficha tras un traslado
    (p. ej. referencia tipo BP-1-26-04-28-000066):

    - Con **valoración automática** y método **AVCO** o **FIFO**, Odoo recalcula el
      coste estándar desde las capas de valoración al validar movimientos internos,
      no es un bug del traslado en sí.
    - La ubicación **Tránsito entre tiendas** debe tener **compañía** coherente
      (`stock_location_inter_store_transit`): si el tránsito queda sin compañía o
      mal configurado, el tratamiento contable del movimiento puede diferir y afectar
      cómo se actualiza el coste.
    - Productos **por lote** con valoración por lote propagan el coste al validar;

    Las notas en el chatter del producto cuando cambia el costo las añade
    ``product_chatter_log`` (incl. contexto de este traslado al validar pickings).

    Al validar envío y recepción se fuerza
    ``l10n_hn_inter_store_transfer_skip_standard_price_update`` para no recalcular
    el coste estándar en ficha (equivalente funcional a transferencia interna pura).
    """
    _name = "stock.inter.store.transfer"
    _description = "Traslado entre Tiendas"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Referencia",
        default="New",
        copy=False,
        readonly=True,
    )
    location_src_id = fields.Many2one(
        "stock.location",
        string="Ubicación Origen",
        required=True,
        domain="[('usage', '=', 'internal')]",
        tracking=True,
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Ubicación Destino",
        required=True,
        domain="[('usage', '=', 'internal')]",
        tracking=True,
    )
    transit_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación Tránsito",
        compute="_compute_transit_location",
        store=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        "stock.inter.store.transfer.line",
        "transfer_id",
        string="Líneas",
    )
    allowed_product_ids = fields.Many2many(
        "product.product",
        string="Productos con stock en origen",
        compute="_compute_allowed_product_ids",
        help="Productos almacenables con cantidad disponible (no reservada) en la ubicación origen.",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmado"),
            ("sent", "Enviado"),
            ("received", "Recibido"),
            ("cancel", "Cancelado"),
        ],
        default="draft",
        copy=False,
        tracking=True,
    )
    date = fields.Datetime(
        string="Fecha Programada",
        default=fields.Datetime.now,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    branch_id = fields.Many2one(
        "res.branch",
        string="Sucursal Origen",
        compute="_compute_branch_ids",
        store=True,
        readonly=True,
        tracking=True,
    )
    branch_dest_id = fields.Many2one(
        "res.branch",
        string="Sucursal Destino",
        compute="_compute_branch_ids",
        store=True,
        readonly=True,
        tracking=True,
    )
    picking_out_id = fields.Many2one(
        "stock.picking",
        string="Envío (Origen)",
        readonly=True,
        copy=False,
    )
    picking_in_id = fields.Many2one(
        "stock.picking",
        string="Recepción (Destino)",
        readonly=True,
        copy=False,
    )
    sent_by_user_id = fields.Many2one(
        "res.users",
        string="Enviado por",
        readonly=True,
        copy=False,
        tracking=True,
    )
    hn_remission_enabled = fields.Boolean(
        string="Guía de remisión",
        tracking=True,
        help="Si está activo, puede generar e imprimir la guía de remisión para este traslado.",
    )
    hn_remission_number = fields.Char(
        string="Número de remisión",
        readonly=True,
        copy=False,
    )
    hn_remission_note = fields.Text(
        string="Observaciones (guía)",
        help="Texto opcional que aparece en el pie del PDF de la guía de remisión.",
    )
    # Búsqueda en listado (mismo criterio que stock.picking: producto/lote de cualquier línea)
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        related="line_ids.product_id",
        readonly=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lote / serie",
        related="line_ids.lot_id",
        readonly=True,
    )

    def _get_branch_for_location(self, location):
        """Obtiene la sucursal asociada a una ubicación."""
        if not location:
            return self.env["res.branch"]
        branch = location.branch_id
        if not branch:
            warehouse = self.env["stock.warehouse"].search(
                [("lot_stock_id", "=", location.id)], limit=1,
            )
            if warehouse and hasattr(warehouse, "branch_id"):
                branch = warehouse.branch_id
        return branch or self.env["res.branch"]

    @api.depends("location_src_id", "location_dest_id")
    def _compute_branch_ids(self):
        for rec in self:
            rec.branch_id = rec._get_branch_for_location(rec.location_src_id)
            rec.branch_dest_id = rec._get_branch_for_location(rec.location_dest_id)

    def _get_products_with_available_qty_in_location(self, location, company=None):
        """Productos product/consu con available_quantity > 0 en la jerarquía de ubicación."""
        self.ensure_one()
        if not location:
            return self.env["product.product"]
        domain = [
            ("location_id", "child_of", location.id),
            ("product_id.type", "in", ("product", "consu")),
        ]
        if company:
            domain.append(("company_id", "in", [False, company.id]))
        quants = self.env["stock.quant"].search(domain)
        # available_quantity = quantity - reserved (coherente con free_qty por ubicación)
        return quants.filtered(lambda q: q.available_quantity > 0.0).mapped("product_id")

    @api.depends("location_src_id", "company_id")
    def _compute_allowed_product_ids(self):
        Product = self.env["product.product"]
        for transfer in self:
            if not transfer.location_src_id:
                transfer.allowed_product_ids = Product
            else:
                transfer.allowed_product_ids = (
                    transfer._get_products_with_available_qty_in_location(
                        transfer.location_src_id, transfer.company_id
                    )
                )

    def _remove_lines_without_stock_in_origin(self):
        """Quita líneas cuyo producto no tenga stock disponible en el origen actual (borrador)."""
        for transfer in self:
            if transfer.state != "draft" or not transfer.location_src_id:
                continue
            allowed_ids = set(transfer.allowed_product_ids.ids)
            bad = transfer.line_ids.filtered(
                lambda l: l.product_id and l.product_id.id not in allowed_ids
            )
            if bad:
                bad.unlink()

    @api.onchange("location_src_id")
    def _onchange_location_src_id(self):
        if not self.location_src_id or not self.line_ids:
            return
        allowed_ids = set(
            self._get_products_with_available_qty_in_location(
                self.location_src_id, self.company_id
            ).ids
        )
        to_remove = self.line_ids.filtered(
            lambda l: l.product_id and l.product_id.id not in allowed_ids
        )
        if not to_remove:
            return
        names = ", ".join(to_remove.mapped("product_id.display_name"))
        to_remove.unlink()
        return {
            "warning": {
                "title": _("Ubicación origen"),
                "message": _(
                    "Se eliminaron líneas cuyo producto no tiene stock disponible "
                    "en la nueva ubicación origen: %s",
                    names,
                ),
            }
        }

    @api.depends("company_id")
    def _compute_transit_location(self):
        for rec in self:
            transit = self.env.ref(
                "l10n_hn_stock.stock_location_inter_store_transit",
                raise_if_not_found=False,
            )
            if transit and (not transit.company_id or transit.company_id == rec.company_id):
                rec.transit_location_id = transit
            else:
                # Fallback: buscar ubicación de tránsito
                rec.transit_location_id = self.env["stock.location"].search(
                    [
                        ("usage", "=", "transit"),
                        "|",
                        ("company_id", "=", rec.company_id.id),
                        ("company_id", "=", False),
                    ],
                    limit=1,
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = "Nuevo"
        transfers = super().create(vals_list)
        transfers._remove_lines_without_stock_in_origin()
        return transfers

    def write(self, vals):
        res = super().write(vals)
        if "location_src_id" in vals:
            self._remove_lines_without_stock_in_origin()
            self.line_ids._ensure_qty_not_exceed_available()
        return res

    def _get_warehouse_for_location(self, location):
        """Obtiene el warehouse asociado a una ubicación."""
        if not location:
            return self.env["stock.warehouse"]
        return self.env["stock.warehouse"].search(
            [("lot_stock_id", "=", location.id)], limit=1,
        ) or self.env["stock.warehouse"].search(
            [("lot_stock_id", "parent_of", location.id)], limit=1,
        )

    def _generate_transfer_name(self, location):
        """Genera nombre con formato WH-M001-26-03-04-00013."""
        import re

        warehouse = self._get_warehouse_for_location(location)
        wh_code = warehouse.code if warehouse else "TET"

        branch_obj = None
        if warehouse and hasattr(warehouse, "branch_id") and warehouse.branch_id:
            branch_obj = warehouse.branch_id
        elif location.branch_id:
            branch_obj = location.branch_id

        branch_code = branch_obj.branch_code if branch_obj else ""

        if branch_obj and getattr(branch_obj, "transfer_sequence_id", False):
            raw_seq = branch_obj.transfer_sequence_id.next_by_id()
        else:
            raw_seq = self.env["ir.sequence"].next_by_code(
                "stock.inter.store.transfer"
            ) or "00000"

        match = re.search(r"(\d+)$", raw_seq)
        seq_number = match.group(1) if match else raw_seq

        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        date_part = now.strftime("%y-%m-%d")

        parts = [wh_code]
        if branch_code:
            parts.append(branch_code)
        parts.append(date_part)
        parts.append(seq_number)
        return "-".join(parts)

    def unlink(self):
        for rec in self:
            if rec.state not in ("draft", "cancel"):
                raise UserError(
                    _("No se puede eliminar un traslado en estado %s.")
                    % dict(self._fields["state"].selection).get(rec.state, rec.state)
                )
        return super().unlink()

    def action_confirm(self):
        """Asignar secuencia y crear los picking A→Transit y Transit→B."""
        for rec in self:
            rec._validate_can_confirm()
            if not rec.name or rec.name == "Nuevo":
                rec.name = rec._generate_transfer_name(rec.location_src_id)
            rec._create_pickings()
            rec.state = "confirmed"
            rec.message_post(
                body=_(
                    "Traslado <strong>Confirmado</strong>. "
                    "Documento listo para enviar. Requiere validación del picking de origen."
                ),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def _validate_can_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Debe agregar al menos una línea de producto."))
        uom_dp = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for line in self.line_ids:
            if line.product_uom_qty <= 0:
                raise UserError(
                    _("La cantidad debe ser positiva en la línea de %s.")
                    % line.product_id.display_name
                )
            if line.product_id.tracking in ("lot", "serial") and line.lot_id:
                free = self.env["stock.quant"]._get_available_quantity(
                    line.product_id,
                    self.location_src_id,
                    lot_id=line.lot_id,
                    strict=True,
                )
                if float_compare(
                    line.product_uom_qty, free, precision_digits=uom_dp
                ) > 0:
                    raise UserError(
                        _(
                            "No hay cantidad suficiente del lote/serie en origen "
                            "para «%(product)s» (lote «%(lot)s»): disponible %(avail)s, "
                            "solicitado %(need)s.",
                            product=line.product_id.display_name,
                            lot=line.lot_id.display_name,
                            avail=free,
                            need=line.product_uom_qty,
                        )
                    )
        self.line_ids._ensure_qty_not_exceed_available()
        # Validar que no haya líneas con producto sin stock en origen
        lines_without_stock = self.line_ids.filtered(lambda l: l.qty_available <= 0)
        if lines_without_stock:
            product_names = "\n• ".join(
                ["%s (Ref: %s)" % (p.display_name, p.default_code or "-")
                 for p in lines_without_stock.mapped("product_id")]
            )
            raise UserError(
                _(
                    "No se puede confirmar el traslado. Los siguientes productos "
                    "no tienen stock disponible en la ubicación origen:\n\n• %(products)s\n\n"
                    "Elimine estas líneas o agregue stock en origen antes de confirmar.",
                    products=product_names,
                )
            )
        if self.location_src_id == self.location_dest_id:
            raise UserError(
                _("La ubicación origen y destino no pueden ser la misma.")
            )
        if not self.transit_location_id:
            raise UserError(
                _("No se encontró una ubicación de tránsito configurada.")
            )

    def _get_picking_type(self, location, direction="out"):
        """Obtener el picking type interno del almacén al que pertenece la ubicación."""
        warehouse = location.warehouse_id if hasattr(location, "warehouse_id") else None
        if not warehouse:
            # Buscar warehouse por jerarquía de ubicaciones
            warehouse = self.env["stock.warehouse"].search(
                [
                    "|",
                    ("lot_stock_id", "parent_of", location.id),
                    ("lot_stock_id", "=", location.id),
                ],
                limit=1,
            )
        if warehouse:
            return warehouse.int_type_id
        return self.env["stock.picking.type"].search(
            [("code", "=", "internal")], limit=1
        )

    def _command_create_move_for_line(
        self, line, location_src, location_dest
    ):
        """Crea un movimiento; si hay lote, añade línea detallada (conserva coste de valoración)."""
        self.ensure_one()
        vals = {
            "description_picking": line.product_id.display_name,
            "product_id": line.product_id.id,
            "product_uom_qty": line.product_uom_qty,
            "product_uom": line.product_uom.id,
            "location_id": location_src.id,
            "location_dest_id": location_dest.id,
        }
        if line.lot_id:
            vals["move_line_ids"] = [
                Command.create(
                    {
                        "product_id": line.product_id.id,
                        "product_uom_id": line.product_uom.id,
                        "location_id": location_src.id,
                        "location_dest_id": location_dest.id,
                        "company_id": self.company_id.id,
                        "lot_id": line.lot_id.id,
                        "quantity": line.product_uom_qty,
                    }
                )
            ]
        return Command.create(vals)

    def _create_pickings(self):
        self.ensure_one()
        StockPicking = self.env["stock.picking"]

        picking_type_out = self._get_picking_type(self.location_src_id, "out")
        picking_type_in = self._get_picking_type(self.location_dest_id, "in")

        if not picking_type_out or not picking_type_in:
            raise UserError(
                _("No se encontró un tipo de operación interna configurado.")
            )

        # Picking 1: Origen → Tránsito
        move_vals_out = []
        for line in self.line_ids:
            move_vals_out.append(
                self._command_create_move_for_line(
                    line,
                    self.location_src_id,
                    self.transit_location_id,
                )
            )

        pick_vals_out = {
            "picking_type_id": picking_type_out.id,
            "location_id": self.location_src_id.id,
            "location_dest_id": self.transit_location_id.id,
            "origin": self.name,
            "scheduled_date": self.date,
            "move_ids": move_vals_out,
            "company_id": self.company_id.id,
        }
        if hasattr(StockPicking, "branch_id") and self.branch_id:
            pick_vals_out["branch_id"] = self.branch_id.id

        picking_out = StockPicking.create(pick_vals_out)
        picking_out.action_confirm()
        picking_out.action_assign()

        # Picking 2: Tránsito → Destino
        move_vals_in = []
        for line in self.line_ids:
            move_vals_in.append(
                self._command_create_move_for_line(
                    line,
                    self.transit_location_id,
                    self.location_dest_id,
                )
            )

        dest_branch = None
        if hasattr(self.location_dest_id, "branch_id") and self.location_dest_id.branch_id:
            dest_branch = self.location_dest_id.branch_id
        elif self.location_dest_id.warehouse_id and hasattr(
            self.location_dest_id.warehouse_id, "branch_id"
        ):
            dest_branch = self.location_dest_id.warehouse_id.branch_id

        pick_vals_in = {
            "picking_type_id": picking_type_in.id,
            "location_id": self.transit_location_id.id,
            "location_dest_id": self.location_dest_id.id,
            "origin": self.name,
            "scheduled_date": self.date,
            "move_ids": move_vals_in,
            "company_id": self.company_id.id,
        }
        if hasattr(StockPicking, "branch_id") and dest_branch:
            pick_vals_in["branch_id"] = dest_branch.id

        picking_in = StockPicking.create(pick_vals_in)
        picking_in.action_confirm()
        picking_in.action_assign()

        self.write(
            {
                "picking_out_id": picking_out.id,
                "picking_in_id": picking_in.id,
            }
        )

    def _apply_move_done_quantities_before_validate(self, picking):
        """Replica la lógica de stock.picking.button_validate para pickings en borrador.

        En Odoo 19, si el albarán ya está confirmado/asignado (no en borrador),
        `button_validate` no copia `product_uom_qty` a `quantity` (hecho), y el
        `_sanity_check` falla con el mensaje de «cantidades cero» / «Set quantities first».
        """
        for move in picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
            if move.product_uom.is_zero(move.quantity) and not move.product_uom.is_zero(
                move.product_uom_qty
            ):
                move.quantity = move.product_uom_qty

    def _sync_picking_effective_date(self, picking):
        """Tras validar, la fecha efectiva debe coincidir con la fecha del traslado (no la hora actual)."""
        self.ensure_one()
        if not picking or picking.state != "done" or not self.date:
            return
        picking.write({"date_done": self.date})

    def _check_user_branch(self, branch, action_name):
        """Verifica que el usuario pertenezca a la sucursal indicada."""
        user = self.env.user
        is_supervisor = user.has_group("l10n_hn_stock.group_transfer_supervisor")
        if is_supervisor:
            return
        user_branches = user.branch_ids | user.branch_id
        if branch and branch not in user_branches:
            raise UserError(
                _(
                    "No tiene permiso para %(action)s este traslado. "
                    "Su usuario no pertenece a la sucursal %(branch)s.",
                    action=action_name,
                    branch=branch.name,
                )
            )

    def _l10n_hn_ctx_traslado_chatter_costos(self, rec, fase):
        """Contexto al validar pickings del traslado: nota opcional en producto + sin recálculo de coste estándar.

        Las transferencias internas no deben modificar el precio de costo de la ficha;
        ``l10n_hn_inter_store_transfer_skip_standard_price_update`` evita ``_update_standard_price``
        (producto y lote) durante esa validación.
        """
        return dict(
            self.env.context,
            l10n_hn_standard_price_chatter_hint=_(
                "Traslado entre tiendas «%(name)s»: %(fase)s.",
                name=rec.name,
                fase=fase,
            ),
            l10n_hn_inter_store_transfer_skip_standard_price_update=True,
        )

    def action_send(self):
        """Validar picking Origen→Tránsito. Los productos salen de A y van a tránsito."""
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(
                    _("Solo se puede enviar un traslado en estado Confirmado.")
                )
            if not self.env.context.get("skip_inter_store_transfer_checks"):
                rec._check_user_branch(rec.branch_id, _("enviar"))
            if not rec.picking_out_id:
                raise UserError(_("No se encontró el picking de envío."))
            rec._apply_move_done_quantities_before_validate(rec.picking_out_id)
            ctx = rec._l10n_hn_ctx_traslado_chatter_costos(
                rec, _("validación envío (origen → tránsito)")
            )
            rec.picking_out_id.with_context(**ctx).button_validate()
            rec._sync_picking_effective_date(rec.picking_out_id)
            if (
                rec.picking_in_id
                and rec.picking_in_id.state not in ("done", "cancel")
            ):
                rec.picking_in_id.action_assign()
            rec.sent_by_user_id = self.env.user
            rec.state = "sent"
            rec.message_post(
                body=_(
                    "Traslado <strong>Enviado</strong> por %s. "
                    "Productos en tránsito. Pendiente de recepción en destino."
                ) % self.env.user.name,
                subtype_xmlid="mail.mt_note",
            )
        return True

    def action_receive(self):
        """Validar picking Tránsito→Destino. Los productos llegan a B."""
        for rec in self:
            if rec.state != "sent":
                raise UserError(
                    _("Solo se puede recibir un traslado en estado Enviado.")
                )
            if not self.env.context.get("skip_inter_store_transfer_checks"):
                rec._check_user_branch(rec.branch_dest_id, _("recibir"))
            is_supervisor = self.env.user.has_group(
                "l10n_hn_stock.group_transfer_supervisor"
            )
            if (
                not self.env.context.get("skip_inter_store_transfer_checks")
                and not is_supervisor
                and rec.sent_by_user_id == self.env.user
            ):
                raise UserError(
                    _(
                        "No puede recibir este traslado porque usted mismo lo envió. "
                        "La recepción debe ser realizada por otro usuario."
                    )
                )
            if not rec.picking_in_id:
                raise UserError(_("No se encontró el picking de recepción."))
            rec._apply_move_done_quantities_before_validate(rec.picking_in_id)
            ctx = rec._l10n_hn_ctx_traslado_chatter_costos(
                rec, _("validación recepción (tránsito → destino)")
            )
            rec.picking_in_id.with_context(**ctx).button_validate()
            rec._sync_picking_effective_date(rec.picking_in_id)
            rec.state = "received"
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "received":
                raise UserError(
                    _("No se puede cancelar un traslado ya recibido.")
                )
            if rec.picking_out_id and rec.picking_out_id.state not in ("cancel", "done"):
                rec.picking_out_id.action_cancel()
            if rec.picking_in_id and rec.picking_in_id.state not in ("cancel", "done"):
                rec.picking_in_id.action_cancel()
            rec.state = "cancel"
        return True

    def action_view_picking_out(self):
        self.ensure_one()
        if not self.picking_out_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.picking_out_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_picking_in(self):
        self.ensure_one()
        if not self.picking_in_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.picking_in_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_draft(self):
        for rec in self:
            if rec.state != "cancel":
                raise UserError(
                    _("Solo se puede revertir un traslado en estado Cancelado.")
                )
            rec.write({
                "state": "draft",
                "picking_out_id": False,
                "picking_in_id": False,
                "hn_remission_number": False,
            })
        return True

    def _validate_remission_generation(self):
        self.ensure_one()
        if not self.hn_remission_enabled:
            raise UserError(_("Active «Guía de remisión» en el traslado para generar el número."))
        if self.hn_remission_number:
            raise UserError(_("La secuencia de remisión ya fue generada."))
        if self.state not in ("confirmed", "sent", "received"):
            raise UserError(
                _("Solo puede generar la guía de remisión con el traslado confirmado o en envío/recepción.")
            )
        if not self.line_ids:
            raise UserError(_("No hay líneas de producto para la guía de remisión."))

    def _get_remission_sequence_next(self):
        """Número siguiente: secuencia de la sucursal origen si existe; si no, hn.remission global."""
        self.ensure_one()
        branch = self.branch_id
        if branch and branch.hn_remission_sequence_id:
            return branch.hn_remission_sequence_id.next_by_id()
        return self.env["ir.sequence"].next_by_code("hn.remission")

    def action_generate_remission_sequence(self):
        self.ensure_one()
        self._validate_remission_generation()
        remission_number = self._get_remission_sequence_next()
        if not remission_number:
            raise UserError(
                _(
                    "No hay número disponible: configure la secuencia global hn.remission "
                    "o la «Secuencia guía de remisión (traslados)» en la sucursal de origen (%s)."
                )
                % (self.branch_id.name if self.branch_id else _("sin sucursal"))
            )
        self.write({"hn_remission_number": remission_number})
        self.message_post(
            body=_("Guía de remisión generada: <strong>%s</strong>") % remission_number,
            subtype_xmlid="mail.mt_note",
        )
        return True

    def action_print_remission_guide(self):
        self.ensure_one()
        if not self.hn_remission_enabled:
            raise UserError(_("Active «Guía de remisión» para imprimir."))
        if not self.hn_remission_number:
            raise UserError(_("Genere la secuencia de remisión antes de imprimir."))
        return self.env.ref(
            "l10n_hn_stock.action_report_remission_inter_store"
        ).report_action(self)
