from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ConsumeProduct(models.Model):
    _name = "consume.product"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Consume Product"

    name = fields.Char(string="Name", default="New", copy=False)
    allowed_picking_type_ids = fields.Many2many(
        comodel_name="stock.picking.type",
        relation="consume_product_allowed_picking_type_rel",
        column1="consume_product_id",
        column2="picking_type_id",
        string="Allowed operation types",
        compute="_compute_allowed_picking_type_ids",
        readonly=True,
    )
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Operation Type",
        check_company=True,
        domain="[('id', 'in', allowed_picking_type_ids)]",
    )
    location_id = fields.Many2one("stock.location", string="Source Location")
    dest_location_id = fields.Many2one("stock.location", string="Destination Location")
    date = fields.Datetime(string="Scheduled Date")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirm", "Confirmed"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        copy=False,
    )
    consume_line = fields.One2many(
        "consume.product.line", "consume_id", string="Consume Lines"
    )
    picking_ids = fields.Many2many("stock.picking", string="Pickings", copy=False)
    is_incoming = fields.Boolean(string="Incoming", default=False)
    notes = fields.Html(string="Notas", sanitize_style=True, copy=False)

    @api.depends("company_id", "is_incoming")
    def _compute_allowed_picking_type_ids(self):
        PickingType = self.env["stock.picking.type"].sudo()
        if "use_in_consume_product" not in PickingType._fields:
            for rec in self:
                rec.allowed_picking_type_ids = False
            return
        for rec in self:
            company = rec.company_id or rec.env.company
            domain = [
                ("use_in_consume_product", "=", True),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ]
            if rec.is_incoming:
                domain.append(("code", "=", "incoming"))
            else:
                domain.append(("code", "=", "internal"))
            rec.allowed_picking_type_ids = PickingType.search(domain)

    @api.constrains("picking_type_id", "is_incoming", "company_id")
    def _check_picking_type_consume_product_flag(self):
        PickingType = self.env["stock.picking.type"]
        if "use_in_consume_product" not in PickingType._fields:
            return
        for rec in self:
            pt = rec.picking_type_id
            if not pt:
                continue
            if not pt.use_in_consume_product:
                raise ValidationError(
                    _(
                        "El tipo de operación debe tener marcado «Productos de consumo» "
                        "en su configuración."
                    )
                )
            expected = "incoming" if rec.is_incoming else "internal"
            if pt.code != expected:
                raise ValidationError(
                    _(
                        "El tipo de operación no corresponde al flujo del documento "
                        "(se esperaba %(expected)s)."
                    )
                    % {"expected": expected}
                )

    @api.model
    def _consume_scheduled_date_to_day(self, vals):
        """Día calendario (usuario TZ) a partir de ``date`` del documento o ahora."""
        sched = vals.get("date")
        if sched:
            dt = fields.Datetime.to_datetime(sched)
        else:
            dt = fields.Datetime.now()
        return fields.Datetime.context_timestamp(self, dt).date()

    @api.model
    def _ensure_sequence_day_range(self, sequence, day):
        """Un rango por día para que el contador reinicie (00001 cada día)."""
        if not sequence.use_date_range:
            return
        day = fields.Date.to_date(day)
        DateRange = self.env["ir.sequence.date_range"].sudo()
        found = DateRange.search(
            [
                ("sequence_id", "=", sequence.id),
                ("date_from", "<=", day),
                ("date_to", ">=", day),
            ],
            limit=1,
        )
        if found:
            return
        DateRange.create(
            {
                "sequence_id": sequence.id,
                "date_from": day,
                "date_to": day,
                "number_next": 1,
            }
        )

    @api.model
    def _get_ir_sequence_for_consume(self, sequence_code, company_id):
        """Secuencia del módulo (evita ir.sequence duplicadas con el mismo código)."""
        xmlids = {
            "consume.product": "gn_consume_product.consume_product_sequence",
            "incoming.product": "gn_consume_product.incoming_product_sequence",
        }
        xid = xmlids.get(sequence_code)
        if xid:
            seq = self.env.ref(xid, raise_if_not_found=False)
            if (
                seq
                and seq.code == sequence_code
                and (not seq.company_id or seq.company_id.id == company_id)
            ):
                return seq.sudo()
        candidates = (
            self.env["ir.sequence"]
            .sudo()
            .search(
                [
                    ("code", "=", sequence_code),
                    ("company_id", "in", [company_id, False]),
                ],
                order="company_id desc, id desc",
            )
        )
        dated = candidates.filtered(lambda s: s.prefix and "%(y)s" in s.prefix)
        return dated[:1] or candidates[:1]

    @api.model
    def _next_consume_document_name(self, vals):
        sequence_code = (
            "incoming.product" if vals.get("is_incoming") else "consume.product"
        )
        company_id = vals.get("company_id") or self.env.company.id
        seq = self._get_ir_sequence_for_consume(sequence_code, company_id)
        day = self._consume_scheduled_date_to_day(vals)
        if seq:
            self._ensure_sequence_day_range(seq, day)
            return seq.next_by_id(sequence_date=day)
        prefix = "PE-" if vals.get("is_incoming") else "PC-"
        y, m, d = day.strftime("%y"), day.strftime("%m"), day.strftime("%d")
        return f"{prefix}{y}-{m}-{d}-00001"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", "New") == "New":
                vals["name"] = self._next_consume_document_name(vals)
            if vals.get("is_incoming"):
                suppliers_location = self.env.ref(
                    "stock.stock_location_suppliers", raise_if_not_found=False
                )
                stock_location = self.env.ref(
                    "stock.stock_location_stock", raise_if_not_found=False
                )
                if suppliers_location and not vals.get("location_id"):
                    vals["location_id"] = suppliers_location.id
                if stock_location and not vals.get("dest_location_id"):
                    vals["dest_location_id"] = stock_location.id
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("Can not delete record in done state."))
        return super().unlink()

    def action_view_picking(self):
        action = self.env.ref("stock.action_picking_tree_all")
        result = action.read()[0]
        result["context"] = {}
        pick_ids = self.picking_ids
        if not pick_ids:
            return result

        result["domain"] = [("id", "in", pick_ids.ids)]
        if len(pick_ids) == 1:
            res = self.env.ref("stock.view_picking_form", False)
            if res:
                result["views"] = [(res.id, "form")]
            result["res_id"] = pick_ids.id
        return result

    @api.onchange("picking_type_id")
    def _onchange_picking_type_id(self):
        if not self.picking_type_id:
            return
        self.location_id = self.picking_type_id.default_location_src_id
        self.dest_location_id = self.picking_type_id.default_location_dest_id
        if self.is_incoming:
            self.location_id = self.env.ref("stock.stock_location_suppliers")
        elif not self.location_id:
            self.location_id = self.picking_type_id.default_location_src_id

        if self.is_incoming:
            self.dest_location_id = self.env.ref("stock.stock_location_stock")
        elif not self.dest_location_id:
            self.dest_location_id = self.picking_type_id.default_location_dest_id

    def write(self, vals):
        return super().write(vals)

    @api.onchange("is_incoming")
    def _onchange_is_incoming(self):
        pt = self.picking_type_id
        if pt:
            wrong_code = (self.is_incoming and pt.code != "incoming") or (
                not self.is_incoming and pt.code != "internal"
            )
            missing_flag = (
                "use_in_consume_product" in pt._fields
                and not pt.use_in_consume_product
            )
            if wrong_code or missing_flag:
                self.picking_type_id = False
        if self.is_incoming:
            suppliers_location = self.env.ref(
                "stock.stock_location_suppliers", raise_if_not_found=False
            )
            stock_location = self.env.ref(
                "stock.stock_location_stock", raise_if_not_found=False
            )
            if suppliers_location:
                self.location_id = suppliers_location
            if stock_location:
                self.dest_location_id = stock_location
        else:
            self._onchange_picking_type_id()

    def action_cancel(self):
        if any(picking.state == "done" for picking in self.picking_ids):
            raise UserError(_("Some pickings are already processed; cannot cancel."))
        self.picking_ids.action_cancel()
        self.picking_ids = [Command.clear()]
        self.state = "cancel"

    def action_set_to_draft(self):
        """Vuelve a borrador cancelando y desvinculando pickings pendientes."""
        for rec in self:
            if rec.state == "done":
                raise UserError(
                    _("No se puede pasar a borrador un documento ya marcado como hecho.")
                )
            if any(picking.state == "done" for picking in rec.picking_ids):
                raise UserError(
                    _(
                        "Hay pickings ya validados; cancele o revierta el inventario "
                        "antes de volver a borrador."
                    )
                )
            open_pickings = rec.picking_ids.filtered(
                lambda p: p.state not in ("done", "cancel")
            )
            if open_pickings:
                open_pickings.action_cancel()
                rec.write(
                    {"picking_ids": [Command.unlink(pid) for pid in open_pickings.ids]}
                )
        self.write({"state": "draft"})
        for rec in self:
            rec.message_post(
                body=_("Documento vuelto a borrador."),
                subtype_xmlid="mail.mt_note",
            )

    def action_confirm(self):
        """Create picking for consume product."""
        self.ensure_one()
        if not self.consume_line:
            raise UserError(_("Please add some lines."))

        open_pickings = self.picking_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
        )
        if open_pickings:
            open_pickings.action_cancel()
            self.write(
                {"picking_ids": [Command.unlink(pid) for pid in open_pickings.ids]}
            )

        move_commands = []
        for line in self.consume_line:
            if line.quantity <= 0:
                raise UserError(_("Quantity must be positive."))
            tracking = line.product_id.tracking
            if tracking in ("lot", "serial") and not line.lot_id:
                raise UserError(
                    _(
                        "El producto %(product)s requiere lote/número de serie; "
                        "indique el lote en la línea."
                    )
                    % {"product": line.product_id.display_name}
                )
            if tracking == "serial" and float_compare(
                line.quantity, 1.0, precision_rounding=line.uom_id.rounding or 0.01
            ):
                raise UserError(
                    _(
                        "Para productos con seguimiento por número de serie, la cantidad "
                        "debe ser 1 por línea (%(product)s)."
                    )
                    % {"product": line.product_id.display_name}
                )
            move_vals = {
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity,
                "product_uom": line.uom_id.id,
                "location_id": self.location_id.id,
                "location_dest_id": self.dest_location_id.id,
            }
            if tracking in ("lot", "serial") and line.lot_id:
                move_vals["move_line_ids"] = [
                    Command.create(
                        {
                            "product_id": line.product_id.id,
                            "quantity": line.quantity,
                            "lot_id": line.lot_id.id,
                        }
                    )
                ]
            if "name" in self.env["stock.move"]._fields:
                move_vals["name"] = line.product_id.display_name
            else:
                move_vals["description_picking"] = line.product_id.display_name
            move_vals = self._prepare_consume_stock_move_vals(move_vals, line)
            move_commands.append(Command.create(move_vals))

        picking_vals = {
            "location_id": self.location_id.id,
            "location_dest_id": self.dest_location_id.id,
            "picking_type_id": self.picking_type_id.id,
            "scheduled_date": self.date,
            "origin": self.name,
            # Nunca usar move_ids_without_package aquí: en l10n_hn_stock es un campo
            # computado (compat. QWeb); solo move_ids crea líneas en Odoo 19.
            "move_ids": move_commands,
        }

        picking_vals["company_id"] = self.company_id.id
        if "product_consume_id" in self.env["stock.picking"]._fields:
            picking_vals["product_consume_id"] = self.id

        picking_vals = self._prepare_consume_stock_picking_vals(picking_vals)
        picking = self.env["stock.picking"].create(picking_vals)
        self.picking_ids = [Command.link(picking.id)]
        self.state = "confirm"
        self.message_post(
            body=_("Consumo confirmado: picking %s") % picking.name,
            subtype_xmlid="mail.mt_note",
        )

    def _prepare_consume_stock_move_vals(self, move_vals, line):
        """Hook para que otros módulos añadan claves al vals del movimiento de stock."""
        self.ensure_one()
        return move_vals

    def _prepare_consume_stock_picking_vals(self, picking_vals):
        """Hook para que otros módulos añadan claves al vals del picking."""
        self.ensure_one()
        return picking_vals

    def action_done(self):
        if not self.picking_ids:
            return
        picking_ids = self.picking_ids.filtered(
            lambda p: p.state not in ("cancel", "done")
        )
        for picking in picking_ids:
            picking.action_confirm()
            moves_needing_assign = picking.move_ids.filtered(
                lambda m: m.state not in ("draft", "cancel", "done")
            )
            if moves_needing_assign:
                picking.action_assign()
            picking.button_validate()
        if picking_ids:
            self.state = "done"


class ConsumeProductLine(models.Model):
    _name = "consume.product.line"
    _description = "Consume Product Line"

    consume_id = fields.Many2one("consume.product", string="Consume Record")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="consume_id.company_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one("product.product", string="Product")
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lote",
        domain="["
        "('product_id', '=', product_id), "
        "'|', ('company_id', '=', False), ('company_id', '=', company_id)"
        "]",
        check_company=True,
    )
    gn_labhospy_supplier_id = fields.Many2one(
        "gn.labhospy.supplier",
        string="Proveedor Labhospy",
        related="product_id.gn_labhospy_supplier_id",
        readonly=True,
    )
    gn_labhospy_catalog_code = fields.Char(
        string="Código catálogo",
        related="product_id.gn_labhospy_catalog_code",
        readonly=True,
    )
    qty_available = fields.Float(
        string="Available", related="product_id.qty_available", readonly=True
    )
    account_id = fields.Many2one("account.account", string="Account")
    quantity = fields.Float(string="Quantity", default=1)
    uom_id = fields.Many2one(
        string="UoM", related="product_id.uom_id", readonly=True
    )

    @api.onchange("product_id")
    def _onchange_product_id_consume_line(self):
        self.lot_id = False
