from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ConsumeProduct(models.Model):
    _inherit = "consume.product"

    consume_branch_ui_locked = fields.Boolean(
        string="Sucursal fijada por usuario",
        compute="_compute_consume_branch_automation_flags",
        help="Si el usuario tiene sucursal en su perfil, no puede cambiarla aquí.",
    )
    consume_consume_automation_locked = fields.Boolean(
        string="Origen, destino y tipo bloqueados (consumo)",
        compute="_compute_consume_branch_automation_flags",
        help="Siempre editable en borrador. El almacén predeterminado solo propone valores iniciales.",
    )
    consumption_reason_type_id = fields.Many2one(
        "l10n_hn.consume.reason.type",
        string="Tipo de motivo de consumo",
        tracking=True,
        check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help="Catálogo definido en Inventario → Configuración → Tipos de motivo de consumo.",
    )
    consumption_reason_note = fields.Char(
        string="Detalle del motivo",
        help="Texto opcional que complementa el tipo seleccionado (referencias, autorización, etc.).",
    )

    def _consume_reason_description(self):
        self.ensure_one()
        parts = []
        if self.consumption_reason_type_id:
            parts.append(self.consumption_reason_type_id.display_name)
        note = (self.consumption_reason_note or "").strip()
        if note:
            parts.append(note)
        return " — ".join(parts) if parts else ""

    @api.depends("is_incoming")
    def _compute_consume_branch_automation_flags(self):
        user_branch = self.env.user.branch_id
        for rec in self:
            if rec.is_incoming:
                rec.consume_branch_ui_locked = False
                rec.consume_consume_automation_locked = False
                continue
            rec.consume_branch_ui_locked = bool(user_branch)
            # El almacén predeterminado solo propone origen, destino y tipo.
            # No bloquea la edición: si no hay almacén, el usuario los indica a mano.
            rec.consume_consume_automation_locked = False

    @api.model
    def _search_consume_picking_type_for_warehouse(self, warehouse_user):
        """Tipo interno marcado para consumo en el almacén del usuario."""
        if not warehouse_user:
            return self.env["stock.picking.type"].browse()
        Pt = self.env["stock.picking.type"].sudo()
        cid = warehouse_user.company_id.id
        dom = [
            ("warehouse_id", "=", warehouse_user.id),
            ("code", "=", "internal"),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", cid),
        ]
        if "use_in_consume_product" in Pt._fields:
            dom.append(("use_in_consume_product", "=", True))
        return Pt.search(dom, limit=1, order="sequence, id")

    @api.model
    def _resolve_consume_picking_type(self, _company, warehouse_user):
        """Tipo interno marcado «Productos de consumo» del almacén del usuario."""
        return self._search_consume_picking_type_for_warehouse(warehouse_user)

    @api.model
    def _consume_stock_defaults(self, branch, company):
        """Origen y tipo desde el almacén predeterminado del usuario; destino Desecho desde la compañía."""
        if not company:
            return {}
        company = company.sudo()
        dest_loc = company.hn_consume_dest_location_id
        user = self.env.user.with_company(company)
        if "property_warehouse_id" not in user._fields:
            return {}
        warehouse_user = user.property_warehouse_id
        if not warehouse_user or not warehouse_user.lot_stock_id:
            return {}
        wh_branch = getattr(warehouse_user, "branch_id", False)
        if branch and wh_branch and branch != wh_branch:
            return {}
        pick_type = self._resolve_consume_picking_type(company, warehouse_user)
        if not dest_loc or not pick_type:
            return {}
        if pick_type.warehouse_id != warehouse_user:
            return {}
        return {
            "location_id": warehouse_user.lot_stock_id.id,
            "dest_location_id": dest_loc.id,
            "picking_type_id": pick_type.id,
        }

    @api.depends("company_id", "is_incoming")
    def _compute_allowed_picking_type_ids(self):
        super()._compute_allowed_picking_type_ids()
        for rec in self:
            if rec.is_incoming:
                continue
            usr = rec.env.user.with_company(rec.company_id)
            wh = (
                usr.property_warehouse_id
                if "property_warehouse_id" in usr._fields
                else False
            )
            pt_wh = rec._resolve_consume_picking_type(rec.company_id, wh)
            if pt_wh:
                if rec.allowed_picking_type_ids:
                    rec.allowed_picking_type_ids |= pt_wh
                else:
                    rec.allowed_picking_type_ids = pt_wh

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("default_is_incoming"):
            return res
        company_id = res.get("company_id") or self.env.company.id
        company = self.env["res.company"].browse(company_id)
        user_branch = self.env.user.branch_id
        if (
            user_branch
            and user_branch.company_id
            and user_branch.company_id.id != company.id
        ):
            user_branch = False
        if user_branch:
            if "branch_id" in fields_list:
                res["branch_id"] = user_branch.id
        branch_id = res.get("branch_id")
        branch = self.env["res.branch"].browse(branch_id) if branch_id else self.env["res.branch"]
        if company:
            patch = self._consume_stock_defaults(branch, company)
            for key, val in patch.items():
                if key in fields_list:
                    res.setdefault(key, val)
        return res

    @api.onchange("branch_id")
    def _onchange_branch_id_consume_automation(self):
        if self.is_incoming:
            return
        branch = self.branch_id if self.branch_id else self.env["res.branch"]
        patch = self._consume_stock_defaults(branch, self.company_id)
        if not self.location_id and patch.get("location_id"):
            self.location_id = patch["location_id"]
        if not self.dest_location_id and patch.get("dest_location_id"):
            self.dest_location_id = patch["dest_location_id"]
        if not self.picking_type_id and patch.get("picking_type_id"):
            self.picking_type_id = patch["picking_type_id"]

    @api.constrains("branch_id")
    def _check_consume_branch_matches_user_profile(self):
        user_branch = self.env.user.branch_id
        if not user_branch:
            return
        for rec in self.filtered(lambda r: not r.is_incoming and not r.gts_no_exigir_sucursal):
            if user_branch.company_id and user_branch.company_id != rec.company_id:
                continue
            if rec.branch_id != user_branch:
                raise ValidationError(
                    _(
                        "La sucursal del documento debe ser la misma que la asignada "
                        "a su usuario (%s)."
                    )
                    % user_branch.display_name
                )

    @api.model
    def _misc_journal_id_for_company(self, company):
        """ID del diario general «Operaciones misceláneas» (o nombre equivalente) en la compañía."""
        if not company:
            return False
        cid = company if isinstance(company, int) else company.id
        Journal = self.env["account.journal"].sudo()
        for name in (
            "Operaciones misceláneas",
            "Operaciones miscelaneas",
        ):
            j = Journal.search(
                [
                    ("company_id", "=", cid),
                    ("type", "=", "general"),
                    ("name", "=", name),
                ],
                limit=1,
            )
            if j:
                return j.id
        j = Journal.search(
            [
                ("company_id", "=", cid),
                ("type", "=", "general"),
                ("name", "ilike", "misceláne"),
            ],
            limit=1,
        )
        return j.id if j else False

    @api.model
    def _default_journal_id(self):
        return self._misc_journal_id_for_company(self.env.company)

    journal_id = fields.Many2one(
        "account.journal",
        string="Inventory Journal",
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        default=_default_journal_id,
    )
    journal_entry_ids = fields.One2many(
        "account.move", "consume_id", string="Journal Entries", readonly=True
    )
    journal_entry_count = fields.Integer(
        string="Journal Entry Count", compute="_compute_journal_entry_count"
    )
    branch_id = fields.Many2one(
        "res.branch",
        string="Sucursal",
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    gts_no_exigir_sucursal = fields.Boolean(
        string="Sucursal Opcional",
        default=False,
        help=(
            "Si está activo, el campo Sucursal deja de ser obligatorio en el picking generado."
        ),
    )

    def _infer_consume_branch_id(self):
        """Sucursal desde ubicación origen, almacén del tipo de operación o ubicación destino."""
        self.ensure_one()
        if self.location_id and getattr(self.location_id, "branch_id", False):
            return self.location_id.branch_id
        wh = self.picking_type_id.warehouse_id if self.picking_type_id else False
        if wh and getattr(wh, "branch_id", False):
            return wh.branch_id
        if self.dest_location_id:
            dest = self.dest_location_id
            if getattr(dest, "branch_id", False):
                return dest.branch_id
            dwh = getattr(dest, "warehouse_id", False)
            if dwh and getattr(dwh, "branch_id", False):
                return dwh.branch_id
        return False

    def _consume_effective_branch(self):
        self.ensure_one()
        return self.branch_id or self._infer_consume_branch_id()

    def _ensure_branch_id_from_locations(self):
        """Antes de confirmar: rellena sucursal en el documento si aún está vacía."""
        self.ensure_one()
        if not self.branch_id:
            branch = self._infer_consume_branch_id()
            if branch:
                self.branch_id = branch

    @api.onchange("location_id", "picking_type_id", "dest_location_id")
    def _onchange_consume_branch_from_location(self):
        if self.location_id and getattr(
            self.location_id, "gts_no_exigir_sucursal", False
        ):
            self.gts_no_exigir_sucursal = True
        branch = self._infer_consume_branch_id()
        if branch:
            self.branch_id = branch

    def _sync_consume_line_accounts_from_reason(self):
        """Salidas en borrador: reparte la cuenta del tipo de motivo en todas las líneas."""
        for rec in self:
            if rec.is_incoming or rec.state != "draft":
                continue
            acc = rec.consumption_reason_type_id.consume_account_id
            if acc and rec.consume_line:
                rec.consume_line.write({"account_id": acc.id})

    @api.onchange("consumption_reason_type_id")
    def _onchange_consumption_reason_type_id_accounts(self):
        if self.is_incoming or self.state != "draft":
            return
        acc = self.consumption_reason_type_id.consume_account_id
        if acc:
            for line in self.consume_line:
                line.account_id = acc

    @api.model_create_multi
    def create(self, vals_list):
        Company = self.env["res.company"]
        for vals in vals_list:
            if not vals.get("journal_id"):
                cid = vals.get("company_id") or self.env.company.id
                jid = self._misc_journal_id_for_company(Company.browse(cid))
                if jid:
                    vals["journal_id"] = jid
            if vals.get("is_incoming"):
                continue
            cid = vals.get("company_id") or self.env.company.id
            company = Company.browse(cid)
            user_branch = self.env.user.branch_id
            if (
                user_branch
                and user_branch.company_id
                and user_branch.company_id.id != company.id
            ):
                user_branch = False
            if user_branch and not vals.get("gts_no_exigir_sucursal"):
                vals["branch_id"] = user_branch.id
            br_id = vals.get("branch_id")
            branch = self.env["res.branch"].browse(br_id) if br_id else self.env["res.branch"]
            patch = self._consume_stock_defaults(branch, company)
            for key, val in patch.items():
                vals.setdefault(key, val)
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("consume_skip_branch_stock_apply"):
            return res
        if "branch_id" in vals:
            to_apply = self.filtered(lambda r: not r.is_incoming)
            for rec in to_apply:
                branch = rec.branch_id if rec.branch_id else self.env["res.branch"]
                patch = self._consume_stock_defaults(branch, rec.company_id)
                if not patch:
                    continue
                updates = {}
                if not rec.location_id and patch.get("location_id"):
                    updates["location_id"] = patch["location_id"]
                if not rec.dest_location_id and patch.get("dest_location_id"):
                    updates["dest_location_id"] = patch["dest_location_id"]
                if not rec.picking_type_id and patch.get("picking_type_id"):
                    updates["picking_type_id"] = patch["picking_type_id"]
                if updates:
                    rec.with_context(consume_skip_branch_stock_apply=True).write(updates)
        if "consumption_reason_type_id" in vals:
            self.filtered(
                lambda r: not r.is_incoming and r.state == "draft"
            )._sync_consume_line_accounts_from_reason()
        return res

    def _ensure_consume_outbound_stock_patch(self):
        """Rellena solo origen, destino o tipo vacíos con el almacén predeterminado, si existe."""
        for rec in self.filtered(lambda r: not r.is_incoming and r.state == "draft"):
            branch = rec.branch_id if rec.branch_id else self.env["res.branch"]
            patch = rec._consume_stock_defaults(branch, rec.company_id)
            if not patch:
                continue
            vals = {}
            if not rec.location_id and patch.get("location_id"):
                vals["location_id"] = patch["location_id"]
            if not rec.dest_location_id and patch.get("dest_location_id"):
                vals["dest_location_id"] = patch["dest_location_id"]
            if not rec.picking_type_id and patch.get("picking_type_id"):
                vals["picking_type_id"] = patch["picking_type_id"]
            if vals:
                rec.write(vals)

    def _validate_consume_outbound_for_confirm(self):
        """Reglas de salida por consumo antes de confirmar."""
        for rec in self.filtered(lambda r: not r.is_incoming):
            if not rec.picking_type_id or not rec.location_id or not rec.dest_location_id:
                raise UserError(
                    _(
                        "Indique la ubicación origen, la ubicación destino y el tipo de operación "
                        "antes de confirmar."
                    )
                )
            if not rec.consumption_reason_type_id:
                raise UserError(
                    _(
                        "Seleccione un tipo de motivo de consumo antes de confirmar "
                        "(Inventario → Configuración → Tipos de motivo de consumo)."
                    )
                )
            if not rec.consumption_reason_type_id.consume_account_id:
                raise UserError(
                    _(
                        "Configure la cuenta contable (consumo) en el tipo de motivo «%s» "
                        "(Inventario → Configuración → Tipos de motivo de consumo)."
                    )
                    % rec.consumption_reason_type_id.display_name
                )
            if rec.location_id.usage != "internal":
                raise UserError(
                    _(
                        "La ubicación origen debe ser de uso «interno». Elija un almacén "
                        "o ubicación interna (no cliente, vista ni proveedor)."
                    )
                )
            pt = rec.picking_type_id
            if pt.code != "internal":
                raise UserError(
                    _(
                        "El tipo de operación de una salida por consumo debe ser interno."
                    )
                )
            if "use_in_consume_product" in pt._fields and not pt.use_in_consume_product:
                raise UserError(
                    _(
                        "El tipo de operación debe tener marcado «Productos de consumo»."
                    )
                )

    def _ensure_misc_journal(self):
        """Fuerza el diario Operaciones misceláneas al confirmar (si está definido en la compañía)."""
        for rec in self:
            jid = rec._misc_journal_id_for_company(rec.company_id)
            if jid:
                rec.journal_id = jid

    def action_confirm(self):
        outbound = self.filtered(lambda r: not r.is_incoming)
        outbound._ensure_consume_outbound_stock_patch()
        outbound._validate_consume_outbound_for_confirm()
        self._ensure_branch_id_from_locations()
        self._ensure_misc_journal()
        res = super().action_confirm()
        for rec in outbound:
            body = rec._consume_reason_description()
            if body:
                rec.message_post(
                    body=_("Motivo del consumo: %s") % body,
                    subtype_xmlid="mail.mt_note",
                )
        return res

    def _prepare_consume_stock_move_vals(self, move_vals, line):
        move_vals = super()._prepare_consume_stock_move_vals(move_vals, line)
        branch = self._consume_effective_branch()
        if branch and "branch_id" in self.env["stock.move"]._fields:
            move_vals["branch_id"] = branch.id
        return move_vals

    def _prepare_consume_stock_picking_vals(self, picking_vals):
        picking_vals = super()._prepare_consume_stock_picking_vals(picking_vals)
        self.ensure_one()
        reason = self._consume_reason_description()
        if reason:
            origin = picking_vals.get("origin") or ""
            picking_vals["origin"] = (
                _("%(doc)s — %(reason)s") % {"doc": origin, "reason": reason}
                if origin
                else reason
            )
        Picking = self.env["stock.picking"]
        loc = self.location_id
        if "gts_no_exigir_sucursal" in Picking._fields:
            picking_vals["gts_no_exigir_sucursal"] = bool(
                self.gts_no_exigir_sucursal
                or (
                    loc
                    and getattr(loc, "gts_no_exigir_sucursal", False)
                )
            )
        branch = self._consume_effective_branch()
        if branch and "branch_id" in Picking._fields:
            picking_vals["branch_id"] = branch.id
        return picking_vals

    def action_done(self):
        """Valida pickings y genera asientos de valoración/consumo cuando corresponda."""
        if len(self) == 1:
            return self._action_done_consume_pickings()
        for record in self:
            record._action_done_consume_pickings()
        return True

    def _action_done_consume_pickings(self):
        self.ensure_one()
        return_action = True
        ctx_regen = self.env.context.get("consume_empty_picking_regenerated")
        if not self.picking_ids:
            if (
                self.consume_line
                and self.state == "confirm"
                and not ctx_regen
            ):
                self.with_context(consume_empty_picking_regenerated=True).action_confirm()
                return self.with_context(
                    consume_empty_picking_regenerated=True
                )._action_done_consume_pickings()
            return True
        pending_pickings = self.picking_ids.filtered(
            lambda picking: picking.state not in ("cancel", "done")
        )
        empty_pending = pending_pickings.filtered(
            lambda p: not p.move_ids and not p.move_line_ids
        )
        if empty_pending:
            empty_pending.action_cancel()
            self.write(
                {"picking_ids": [Command.unlink(pid) for pid in empty_pending.ids]}
            )
        pending_pickings = self.picking_ids.filtered(
            lambda picking: picking.state not in ("cancel", "done")
        )
        pending_pickings = pending_pickings.filtered(
            lambda p: p.move_ids or p.move_line_ids
        )
        if not pending_pickings:
            all_closed = not self.picking_ids.filtered(
                lambda p: p.state not in ("cancel", "done")
            )
            any_done = bool(self.picking_ids.filtered(lambda p: p.state == "done"))
            if all_closed and any_done and self.state != "done":
                self.write({"state": "done"})
                self._create_account_moves()
                return return_action
            if (
                self.consume_line
                and self.state == "confirm"
                and not ctx_regen
            ):
                # Regenera un picking con movimientos (p. ej. bug antiguo o lista vacía).
                self.with_context(consume_empty_picking_regenerated=True).action_confirm()
                return self.with_context(
                    consume_empty_picking_regenerated=True
                )._action_done_consume_pickings()
            if self.consume_line:
                raise UserError(
                    _(
                        "El picking vinculado estaba vacío o no tiene movimientos. "
                        "Use «Cancelar» en este documento y luego «Confirmar» de nuevo "
                        "para generar un nuevo traslado, o abra «Pickings» y revise el estado."
                    )
                )
            return True
        for picking in pending_pickings:
            picking.action_confirm()
            # action_assign() exige movimientos no draft/cancel/done; si ya están
            # reservados (p. ej. líneas con lote al crear), Odoo avisa "Nothing to check..."
            moves_needing_assign = picking.move_ids.filtered(
                lambda m: m.state not in ("draft", "cancel", "done")
            )
            if moves_needing_assign:
                picking.action_assign()
            res = picking.button_validate()
            if picking.state != "done":
                return res if isinstance(res, dict) else True
            if isinstance(res, dict):
                return_action = res
        if self.state != "done":
            all_closed = not self.picking_ids.filtered(
                lambda p: p.state not in ("cancel", "done")
            )
            any_done = bool(self.picking_ids.filtered(lambda p: p.state == "done"))
            if all_closed and any_done:
                self.write({"state": "done"})
                self._create_account_moves()
        return return_action

    def _create_account_moves(self):
        for record in self:
            if record.journal_entry_ids:
                continue
            if not record.consume_line:
                continue

            company = record.company_id
            currency = company.currency_id
            moves_by_journal = {}
            had_positive_qty = False

            for line in record.consume_line:
                if line.quantity <= 0:
                    continue
                had_positive_qty = True
                if not line.account_id:
                    raise UserError(_("Please set an account on each consume line."))

                product = line.product_id.with_company(company)
                category = product.categ_id
                tmpl_account = (
                    getattr(
                        product.product_tmpl_id,
                        "property_stock_valuation_account_id",
                        False,
                    )
                    if product.product_tmpl_id
                    else False
                )
                inventory_account = tmpl_account or category.property_stock_valuation_account_id
                if not inventory_account:
                    raise UserError(
                        _(
                            "The product %(product)s does not have an inventory valuation account configured."
                        )
                        % {"product": product.display_name}
                    )

                journal = record.journal_id or category.property_stock_journal
                if not journal and hasattr(company, "stock_journal_id"):
                    journal = company.stock_journal_id
                if not journal:
                    raise UserError(
                        _(
                            "No stock journal configured for the product category %(category)s."
                        )
                        % {"category": category.display_name}
                    )

                cost_price = product.standard_price
                amount = currency.round(line.quantity * cost_price)
                if currency.is_zero(amount):
                    continue

                move_vals = moves_by_journal.setdefault(
                    journal.id,
                    {
                        "ref": record.name,
                        "date": fields.Date.context_today(record),
                        "journal_id": journal.id,
                        "company_id": company.id,
                        "line_ids": [],
                    },
                )

                debit_account = line.account_id
                credit_account = inventory_account
                if record.is_incoming:
                    debit_account, credit_account = credit_account, debit_account

                debit_line_vals = {
                    "account_id": debit_account.id,
                    "name": product.display_name,
                    "debit": amount,
                    "credit": 0.0,
                    "company_id": company.id,
                    "product_id": product.id,
                    "quantity": line.quantity,
                }
                credit_line_vals = {
                    "account_id": credit_account.id,
                    "name": product.display_name,
                    "debit": 0.0,
                    "credit": amount,
                    "company_id": company.id,
                    "product_id": product.id,
                    "quantity": line.quantity,
                }

                move_vals["line_ids"].append(Command.create(debit_line_vals))
                move_vals["line_ids"].append(Command.create(credit_line_vals))

            if not moves_by_journal:
                if had_positive_qty:
                    raise UserError(
                        _(
                            "No se generó ningún asiento contable porque el importe total "
                            "es cero. Configure el coste estándar de los productos o revise las cantidades."
                        )
                    )
                continue

            moves_vals = list(moves_by_journal.values())
            for vals in moves_vals:
                vals["consume_id"] = record.id

            account_moves = self.env["account.move"].create(moves_vals)
            account_moves.action_post()
            record.journal_entry_ids = [
                Command.link(move.id) for move in account_moves
            ]

    def _compute_journal_entry_count(self):
        for record in self:
            record.journal_entry_count = len(record.journal_entry_ids)

    def action_view_journal_entries(self):
        self.ensure_one()
        action = self.env.ref("account.action_move_journal_line").read()[0]
        action["domain"] = [("id", "in", self.journal_entry_ids.ids)]
        action["context"] = {"default_consume_id": self.id}
        return action


class ConsumeProductLine(models.Model):
    _inherit = "consume.product.line"

    # Repetidos aquí a propósito: si el servidor actualiza solo l10n_hn_stock y
    # gn_consume_product sigue desactualizado, el cliente web necesita estos
    # campos en el modelo (las vistas de Honduras los muestran).
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lote",
        domain="[('product_id', '=', product_id)]",
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
    account_id = fields.Many2one("account.account", string="Account", required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("account_id"):
                continue
            cid = vals.get("consume_id")
            if not cid:
                continue
            consume = self.env["consume.product"].browse(cid)
            if consume.exists() and not consume.is_incoming:
                acc = consume.consumption_reason_type_id.consume_account_id
                if acc:
                    vals["account_id"] = acc.id
        return super().create(vals_list)

    @api.onchange("product_id")
    def _onchange_product_id_l10n_clear_lot(self):
        self.lot_id = False
        if (
            self.consume_id
            and not self.consume_id.is_incoming
            and not self.account_id
            and self.consume_id.consumption_reason_type_id
        ):
            acc = self.consume_id.consumption_reason_type_id.consume_account_id
            if acc:
                self.account_id = acc

    def _l10n_hn_exit_report_expiry_datetime(self):
        """Datetime para columna «Vencimiento» del PDF de salida de bodega."""
        self.ensure_one()
        lot = self.lot_id
        if lot:
            if lot.expiration_date:
                return lot.expiration_date
            if getattr(lot, "removal_date", False):
                return lot.removal_date
            if getattr(lot, "use_date", False):
                return lot.use_date
        consume = self.consume_id
        if not consume or not consume.picking_ids:
            return False
        picking = consume.picking_ids[:1]
        product = self.product_id
        lines = picking.move_line_ids.filtered(lambda ml: ml.product_id == product)
        if not lines:
            for move in picking.move_ids.filtered(lambda m: m.product_id == product):
                lines |= move.move_line_ids
        for ml in lines:
            if lot and ml.lot_id and ml.lot_id != lot:
                continue
            ml_exp = getattr(ml, "expiration_date", False)
            if ml_exp:
                return ml_exp
            cand_lot = ml.lot_id
            if cand_lot:
                cand = (
                    cand_lot.expiration_date
                    or getattr(cand_lot, "removal_date", False)
                    or getattr(cand_lot, "use_date", False)
                )
                if cand:
                    return cand
        return False

    def _l10n_hn_exit_report_expiry_label(self):
        """Texto ya localizado para el PDF (vacío si no hay fecha)."""
        self.ensure_one()
        dt = self._l10n_hn_exit_report_expiry_datetime()
        if not dt:
            return ""
        from odoo.tools import format_datetime

        return format_datetime(self.env, dt, tz=self.env.user.tz, dt_format="short")
