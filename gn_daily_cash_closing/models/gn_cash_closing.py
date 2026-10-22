# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class GnCashClosing(models.Model):
    _name = "gn.cash.closing"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Cierre de Caja"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        readonly=True,
        copy=False,
        default="/",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("in_progress", "En Proceso"),
            ("done", "Finalizado"),
            ("cancel", "Anulado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )
    date = fields.Date(string="Día", required=True)
    branch_id = fields.Many2one(
        "res.branch", string="Sucursal", required=True,
    )
    user_id = fields.Many2one(
        "res.users", string="Vendedor",
        help="Filtrar cierre por vendedor. Si está vacío, incluye todos los vendedores.",
    )
    observaciones = fields.Text(string="Observaciones")
    remesa_line_ids = fields.One2many(
        "gn.cash.closing.remesa.line", "closing_id",
        string="Remesas Bancarias",
    )
    remesa_sobrante_line_ids = fields.One2many(
        "gn.cash.closing.remesa.sobrante.line", "closing_id",
        string="Remesas Sobrantes",
    )
    # Many2many almacenados (no computados)
    invoice_open_ids = fields.Many2many(
        "account.move",
        "gn_cash_closing_invoice_open_rel",
        "closing_id", "move_id",
        string="Facturas Abiertas",
    )
    invoice_paid_ids = fields.Many2many(
        "account.move",
        "gn_cash_closing_invoice_paid_rel",
        "closing_id", "move_id",
        string="Facturas Pagadas",
    )
    invoice_cancelled_ids = fields.Many2many(
        "account.move",
        "gn_cash_closing_invoice_cancelled_rel",
        "closing_id", "move_id",
        string="Facturas Anuladas",
    )
    payment_posted_ids = fields.Many2many(
        "account.payment",
        "gn_cash_closing_payment_posted_rel",
        "closing_id", "payment_id",
        string="Pagos Realizados",
    )
    payment_cancelled_ids = fields.Many2many(
        "account.payment",
        "gn_cash_closing_payment_cancelled_rel",
        "closing_id", "payment_id",
        string="Pagos Anulados",
    )
    advance_ids = fields.Many2many(
        "account.payment",
        "gn_cash_closing_advance_rel",
        "closing_id", "payment_id",
        string="Anticipos",
    )
    advance_presupuesto_ids = fields.Many2many(
        "account.payment",
        "gn_cash_closing_advance_presupuesto_rel",
        "closing_id", "payment_id",
        string="Anticipos (Cotización Presupuesto)",
    )
    advance_prefactura_ids = fields.Many2many(
        "account.payment",
        "gn_cash_closing_advance_prefactura_rel",
        "closing_id", "payment_id",
        string="Anticipos Pre-Factura",
    )
    can_edit = fields.Boolean(
        compute="_compute_can_edit",
        help="True si el usuario tiene permiso para editar remesas y observaciones",
    )
    can_restore_to_draft = fields.Boolean(
        compute="_compute_can_restore_to_draft",
        help="True si el usuario puede restablecer a borrador",
    )


    def write(self, vals):
        """Invalidar closing_line_sequence de pagos y facturas cuando cambian las listas."""
        seq_fields = (
            "payment_posted_ids", "payment_cancelled_ids", "advance_ids",
            "advance_presupuesto_ids", "advance_prefactura_ids",
            "invoice_open_ids", "invoice_paid_ids", "invoice_cancelled_ids",
        )
        if any(f in vals for f in seq_fields):
            payments = self.env["account.payment"]
            moves = self.env["account.move"]
            for rec in self:
                payments |= (
                    rec.payment_posted_ids | rec.payment_cancelled_ids | rec.advance_ids
                    | rec.advance_presupuesto_ids | rec.advance_prefactura_ids
                )
                moves |= rec.invoice_open_ids | rec.invoice_paid_ids | rec.invoice_cancelled_ids
            res = super().write(vals)
            # Invalidate also the new records (after write)
            for rec in self:
                payments |= (
                    rec.payment_posted_ids | rec.payment_cancelled_ids | rec.advance_ids
                    | rec.advance_presupuesto_ids | rec.advance_prefactura_ids
                )
                moves |= rec.invoice_open_ids | rec.invoice_paid_ids | rec.invoice_cancelled_ids
            if payments:
                payments.invalidate_recordset(["closing_line_sequence"])
            if moves:
                moves.invalidate_recordset(["closing_line_sequence"])
            return res
        return super().write(vals)

    move_id = fields.Many2one(
        "account.move",
        string="Asiento Generado",
        copy=False,
        help="Asiento de depósito generado desde este cierre",
    )
    # Campos computados para pestaña Resumen
    resumen_ventas_contado = fields.Float(compute="_compute_resumen_data", string="Ventas Contado")
    resumen_ventas_contra_entrega = fields.Float(compute="_compute_resumen_data", string="Contra Entrega")
    resumen_ventas_creditos = fields.Float(compute="_compute_resumen_data", string="Créditos")
    resumen_ventas_total = fields.Float(compute="_compute_resumen_data", string="Total Ventas")
    resumen_anulaciones_ventas = fields.Float(compute="_compute_resumen_data", string="Ventas Anuladas")
    resumen_anulaciones_anticipos = fields.Float(compute="_compute_resumen_data", string="Anticipos por Anulaciones")
    resumen_anulaciones_rebajas = fields.Float(compute="_compute_resumen_data", string="Rebajas a Clientes")
    resumen_ingresos_efectivo = fields.Float(compute="_compute_resumen_data", string="Efectivo")
    resumen_ingresos_tarjeta = fields.Float(compute="_compute_resumen_data", string="Tarjeta")
    resumen_ingresos_transferencia = fields.Float(compute="_compute_resumen_data", string="Transferencia")
    resumen_ingresos_anticipos = fields.Float(compute="_compute_resumen_data", string="Anticipos Recibidos")
    resumen_ingresos_sobrantes = fields.Float(compute="_compute_resumen_data", string="Sobrantes Recibidos")
    resumen_ingresos_total = fields.Float(compute="_compute_resumen_data", string="Total Ingresos")
    resumen_remesado_total = fields.Float(compute="_compute_resumen_data", string="Total Remesado")
    resumen_remesado_de_mas = fields.Float(compute="_compute_resumen_data", string="Remesado de Más")
    resumen_no_remesado = fields.Float(compute="_compute_resumen_data", string="No Remesado")
    resumen_liquidacion_monto = fields.Float(compute="_compute_resumen_data", string="Monto Liquidado")
    resumen_liquidacion_remesado = fields.Float(compute="_compute_resumen_data", string="Valor Remesado")
    resumen_liquidacion_no_remesado = fields.Float(compute="_compute_resumen_data", string="Valor No Remesado")
    resumen_liquidacion_cortes = fields.Integer(compute="_compute_resumen_data", string="No. Corte Liquidados")

    # Cierre Inicial (digitado en wizard) - persistido para comparativa
    cierre_inicial_efectivo = fields.Float(string="Cierre Inicial Efectivo", digits=(16, 2), default=0)
    cierre_inicial_tarjeta = fields.Float(string="Cierre Inicial Tarjeta", digits=(16, 2), default=0)
    cierre_inicial_transferencia = fields.Float(string="Cierre Inicial Transferencia", digits=(16, 2), default=0)
    # Diferencias y visibilidad
    cierre_inicial_efectivo_diferencia = fields.Float(
        compute="_compute_cierre_inicial_diferencias", string="Diferencia Efectivo", digits=(16, 2)
    )
    cierre_inicial_tarjeta_diferencia = fields.Float(
        compute="_compute_cierre_inicial_diferencias", string="Diferencia Tarjeta", digits=(16, 2)
    )
    cierre_inicial_transferencia_diferencia = fields.Float(
        compute="_compute_cierre_inicial_diferencias", string="Diferencia Transferencia", digits=(16, 2)
    )
    cierre_inicial_efectivo_falta = fields.Boolean(
        compute="_compute_cierre_inicial_diferencias", help="True si diferencia efectivo < 0"
    )
    cierre_inicial_tarjeta_falta = fields.Boolean(
        compute="_compute_cierre_inicial_diferencias", help="True si diferencia tarjeta < 0"
    )
    cierre_inicial_transferencia_falta = fields.Boolean(
        compute="_compute_cierre_inicial_diferencias", help="True si diferencia transferencia < 0"
    )
    has_cierre_inicial = fields.Boolean(
        compute="_compute_has_cierre_inicial",
        help="True si este cierre tiene datos del Cierre Inicial a Ciegas",
    )
    cierre_inicial_diferencia_total = fields.Float(
        compute="_compute_cierre_inicial_diferencias",
        string="Diferencia (Total Ingresos - Efectivo - Tarjeta)",
        digits=(16, 2),
        help="Total Ingresos - (Diferencia Efectivo + Diferencia Tarjeta)",
    )
    cierre_inicial_diferencia_efectivo_tarjeta = fields.Float(
        compute="_compute_cierre_inicial_diferencias",
        string="Diferencia (Efectivo + Tarjeta)",
        digits=(16, 2),
        help="Suma de Diferencia Efectivo + Diferencia Tarjeta",
    )
    cierre_inicial_diferencia_efectivo_tarjeta_falta = fields.Boolean(
        compute="_compute_cierre_inicial_diferencias",
        help="True si suma de diferencias efectivo+tarjeta < 0",
    )

    @api.depends(
        "cierre_inicial_efectivo", "cierre_inicial_tarjeta", "cierre_inicial_transferencia",
        "resumen_ingresos_efectivo", "resumen_ingresos_tarjeta", "resumen_ingresos_transferencia",
        "resumen_ingresos_total",
    )
    def _compute_cierre_inicial_diferencias(self):
        for rec in self:
            rec.cierre_inicial_efectivo_diferencia = (
                (rec.cierre_inicial_efectivo or 0) - (rec.resumen_ingresos_efectivo or 0)
            )
            rec.cierre_inicial_tarjeta_diferencia = (
                (rec.cierre_inicial_tarjeta or 0) - (rec.resumen_ingresos_tarjeta or 0)
            )
            rec.cierre_inicial_transferencia_diferencia = (
                (rec.cierre_inicial_transferencia or 0) - (rec.resumen_ingresos_transferencia or 0)
            )
            rec.cierre_inicial_diferencia_efectivo_tarjeta = (
                rec.cierre_inicial_efectivo_diferencia + rec.cierre_inicial_tarjeta_diferencia
            )
            rec.cierre_inicial_diferencia_efectivo_tarjeta_falta = (
                rec.cierre_inicial_diferencia_efectivo_tarjeta < 0
            )
            # Diferencia = Total Ingresos - (Diferencia Efectivo + Diferencia Tarjeta)
            rec.cierre_inicial_diferencia_total = (
                (rec.resumen_ingresos_total or 0)
                - (rec.cierre_inicial_efectivo_diferencia + rec.cierre_inicial_tarjeta_diferencia)
            )
            rec.cierre_inicial_efectivo_falta = rec.cierre_inicial_efectivo_diferencia < 0
            rec.cierre_inicial_tarjeta_falta = rec.cierre_inicial_tarjeta_diferencia < 0
            rec.cierre_inicial_transferencia_falta = rec.cierre_inicial_transferencia_diferencia < 0

    @api.depends("cierre_inicial_efectivo", "cierre_inicial_tarjeta", "cierre_inicial_transferencia")
    def _compute_has_cierre_inicial(self):
        for rec in self:
            rec.has_cierre_inicial = bool(
                (rec.cierre_inicial_efectivo or 0) != 0
                or (rec.cierre_inicial_tarjeta or 0) != 0
                or (rec.cierre_inicial_transferencia or 0) != 0
            )

    @api.depends(
        "date", "branch_id", "user_id", "remesa_line_ids", "remesa_line_ids.amount",
        "remesa_sobrante_line_ids", "remesa_sobrante_line_ids.amount",
    )
    def _compute_resumen_data(self):
        report = self.env["report.gn_daily_cash_closing.cash_closing_template"]
        for rec in self:
            if not rec.date or not rec.branch_id:
                for f in [
                    "resumen_ventas_contado", "resumen_ventas_contra_entrega", "resumen_ventas_creditos",
                    "resumen_ventas_total", "resumen_anulaciones_ventas", "resumen_anulaciones_anticipos",
                    "resumen_anulaciones_rebajas", "resumen_ingresos_efectivo", "resumen_ingresos_tarjeta",
                    "resumen_ingresos_transferencia", "resumen_ingresos_anticipos", "resumen_ingresos_sobrantes",
                    "resumen_ingresos_total", "resumen_remesado_total", "resumen_remesado_de_mas",
                    "resumen_no_remesado", "resumen_liquidacion_monto", "resumen_liquidacion_remesado",
                    "resumen_liquidacion_no_remesado",
                ]:
                    rec[f] = 0.0
                rec.resumen_liquidacion_cortes = 0
                continue
            remesas_data = [
                {"bank_name": r.bank_name or "", "account_number": r.account_number or "",
                 "reference": r.reference or "", "date": str(r.date) if r.date else "", "amount": r.amount or 0}
                for r in rec.remesa_line_ids
            ]
            uid = rec.user_id.id if rec.user_id else False
            ventas = report._get_ventas(rec.date, rec.branch_id.id, user_id=uid)
            ingresos = report._get_ingresos(rec.date, rec.branch_id.id, user_id=uid)
            remesas_sobrantes = sum(rec.remesa_sobrante_line_ids.mapped("amount") or [0])
            ingresos["sobrantes"] = ingresos.get("sobrantes", 0) + remesas_sobrantes
            ingresos["total"] = ingresos.get("total", 0) + remesas_sobrantes
            anulaciones = report._get_anulaciones(rec.date, rec.branch_id.id, user_id=uid)
            remesado = report._get_remesado(ingresos, remesas_data)
            liquidacion = report._get_liquidacion(rec.date, rec.branch_id.id)
            rec.resumen_ventas_contado = ventas.get("contado", 0)
            rec.resumen_ventas_contra_entrega = ventas.get("contra_entrega", 0)
            rec.resumen_ventas_creditos = ventas.get("creditos", 0)
            rec.resumen_ventas_total = ventas.get("total", 0)
            rec.resumen_anulaciones_ventas = anulaciones.get("ventas_anuladas", 0)
            rec.resumen_anulaciones_anticipos = anulaciones.get("anticipos_anulaciones", 0)
            rec.resumen_anulaciones_rebajas = anulaciones.get("rebajas_clientes", 0)
            rec.resumen_ingresos_efectivo = ingresos.get("efectivo", 0)
            rec.resumen_ingresos_tarjeta = ingresos.get("tarjeta", 0)
            rec.resumen_ingresos_transferencia = ingresos.get("transferencia", 0)
            rec.resumen_ingresos_anticipos = ingresos.get("anticipos", 0)
            rec.resumen_ingresos_sobrantes = ingresos.get("sobrantes", 0)
            rec.resumen_ingresos_total = ingresos.get("total", 0)
            rec.resumen_remesado_total = remesado.get("total_remesado", 0)
            rec.resumen_remesado_de_mas = remesado.get("remesado_de_mas", 0)
            rec.resumen_no_remesado = remesado.get("no_remesado", 0)
            rec.resumen_liquidacion_monto = ingresos.get("tarjeta", 0)
            rec.resumen_liquidacion_remesado = liquidacion.get("valor_remesado", 0)
            rec.resumen_liquidacion_no_remesado = liquidacion.get("valor_no_remesado", 0)
            rec.resumen_liquidacion_cortes = liquidacion.get("no_corte_liquidados", 0)

    @api.depends("state")
    def _compute_can_edit(self):
        for rec in self:
            rec.can_edit = (
                rec.state in ("draft", "in_progress")
                and self.env.user.has_group(
                    "gn_daily_cash_closing.group_cash_closing_edit"
                )
            )

    @api.depends("state")
    def _compute_can_restore_to_draft(self):
        for rec in self:
            rec.can_restore_to_draft = (
                rec.state == "cancel"
                and self.env.user.has_group(
                    "gn_daily_cash_closing.group_cash_closing_restore_draft"
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                seq_date = vals.get("date") or fields.Date.context_today(self)
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_context(ir_sequence_date=seq_date)
                    .next_by_code("gn.cash.closing", sequence_date=seq_date)
                ) or "/"
        return super().create(vals_list)

    def action_confirm(self):
        """Pasa de Borrador a En Proceso."""
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Solo se puede confirmar un cierre en estado Borrador."))
        return self.write({"state": "in_progress"})

    def action_done(self):
        """Pasa de En Proceso a Finalizado."""
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(
                    _("Solo se puede finalizar un cierre en estado En Proceso.")
                )
        return self.write({"state": "done"})

    def action_cancel(self):
        """Anula el cierre."""
        for rec in self:
            if rec.state == "cancel":
                raise UserError(_("El cierre ya está anulado."))
        return self.write({"state": "cancel"})

    def action_restore_to_draft(self):
        """Restablece a Borrador (requiere permiso)."""
        for rec in self:
            if rec.state != "cancel":
                raise UserError(
                    _("Solo se puede restablecer a borrador un cierre anulado.")
                )
            if not rec.can_restore_to_draft:
                raise UserError(
                    _("No tiene permiso para restablecer cierres a borrador.")
                )
        return self.write({"state": "draft"})

    def _filter_by_user(self, records, model_type="move"):
        """Filtra registros por vendedor si user_id está definido en el cierre.
        - move: filtra account.move por invoice_user_id
        - payment: filtra account.payment por facturas reconciliadas del vendedor
        - advance: filtra anticipos por sale_order.user_id
        """
        if not self.user_id:
            return records
        uid = self.user_id.id
        if model_type == "move":
            return records.filtered(lambda r: r.invoice_user_id.id == uid)
        if model_type == "payment":
            return records.filtered(
                lambda p: any(inv.invoice_user_id.id == uid for inv in p.reconciled_invoice_ids)
            )
        if model_type == "advance":
            def _advance_belongs(pay):
                orders = self.env["sale.order"]
                if "sale_order_id" in pay._fields and pay.sale_order_id:
                    orders |= pay.sale_order_id
                if "sale_order_advance_link_ids" in pay._fields and pay.sale_order_advance_link_ids:
                    orders |= pay.sale_order_advance_link_ids.mapped("sale_order_id")
                return any(o.user_id.id == uid for o in orders)
            return records.filtered(_advance_belongs)
        return records

    def action_load_data(self):
        """Carga los datos de facturas y pagos según fecha, sucursal y vendedor."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(
                _("Solo puede obtener datos cuando el cierre está en estado Borrador.")
            )
        if not self.date or not self.branch_id:
            raise ValidationError(
                _("Debe tener fecha y sucursal antes de obtener los datos.")
            )
        Move = self.env["account.move"]
        Payment = self.env["account.payment"]
        branch_id = self.branch_id.id
        report_date = self.date

        # Facturas abiertas
        inv_open = Move.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "!=", "paid"),
            ("branch_id", "=", branch_id),
        ])
        inv_open = inv_open.filtered(
            lambda m: (m.invoice_date or m.date) == report_date
        )
        self.invoice_open_ids = self._filter_by_user(inv_open, "move")

        # Facturas pagadas
        inv_paid = Move.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "=", "paid"),
            ("branch_id", "=", branch_id),
        ])
        inv_paid = inv_paid.filtered(
            lambda m: (m.invoice_date or m.date) == report_date
        )
        self.invoice_paid_ids = self._filter_by_user(inv_paid, "move")

        # Facturas anuladas
        inv_cancelled = Move.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "cancel"),
            ("branch_id", "=", branch_id),
        ])
        inv_cancelled = inv_cancelled.filtered(
            lambda m: (m.invoice_date or m.date) == report_date
        )
        self.invoice_cancelled_ids = self._filter_by_user(inv_cancelled, "move")

        # Pagos realizados
        pay_posted = Payment.search([
            ("payment_type", "=", "inbound"),
            ("state", "in", ["in_process", "paid"]),
            ("date", "=", report_date),
            ("branch_id", "=", branch_id),
        ])
        self.payment_posted_ids = self._filter_by_user(pay_posted, "payment")

        # Pagos anulados
        pay_cancelled = Payment.search([
            ("payment_type", "=", "inbound"),
            ("state", "=", "canceled"),
            ("date", "=", report_date),
            ("branch_id", "=", branch_id),
        ])
        self.payment_cancelled_ids = self._filter_by_user(pay_cancelled, "payment")

        # Anticipos: separar por estado de cotización vinculada
        if "is_advance" in Payment._fields:
            advances = Payment.search([
                ("payment_type", "=", "inbound"),
                ("is_advance", "=", True),
                ("state", "in", ["in_process", "paid"]),
                ("date", "=", report_date),
                ("branch_id", "=", branch_id),
            ])
            advances = self._filter_by_user(advances, "advance")
            self.advance_ids = advances
            presupuesto = self.env["account.payment"]
            prefactura = self.env["account.payment"]
            for pay in advances:
                orders = self.env["sale.order"]
                if "sale_order_id" in pay._fields and pay.sale_order_id:
                    orders |= pay.sale_order_id
                if "sale_order_advance_link_ids" in pay._fields and pay.sale_order_advance_link_ids:
                    orders |= pay.sale_order_advance_link_ids.mapped("sale_order_id")
                if any(o.state == "sale" for o in orders):
                    prefactura |= pay
                else:
                    presupuesto |= pay
            self.advance_presupuesto_ids = presupuesto
            self.advance_prefactura_ids = prefactura
        else:
            self.advance_ids = Payment
            self.advance_presupuesto_ids = Payment
            self.advance_prefactura_ids = self.env["account.payment"]

    def action_load_remesas_from_system(self):
        """Carga remesas del día desde debit.credit (depósitos) y bank.transfer."""
        self.ensure_one()
        if self.state not in ("draft", "in_progress"):
            raise UserError(
                _("Solo puede cargar remesas cuando el cierre está en Borrador o En Proceso.")
            )
        if not self.can_edit:
            raise UserError(
                _("No tiene permiso para editar las remesas de este cierre.")
            )
        if not self.date or not self.branch_id:
            raise ValidationError(
                _("Debe tener fecha y sucursal antes de cargar remesas.")
            )
        report_date = self.date
        branch_id = self.branch_id.id
        new_line_vals = []

        # debit.credit con move_type='deposit'
        try:
            DebitCredit = self.env["debit.credit"]
            dc_domain = [
                ("move_type", "=", "deposit"),
                ("state", "=", "validated"),
                ("date", "=", report_date),
            ]
            if branch_id:
                dc_domain.append(("branch_id", "=", branch_id))
            deposits = DebitCredit.search(dc_domain, order="name")
            for dc in deposits:
                journal = dc.journal_id
                account_number = ""
                bank_name = journal.name if journal else dc.name or _("Depósito")
                if journal and hasattr(journal, "bank_account_id") and journal.bank_account_id:
                    ba = journal.bank_account_id
                    bank_name = f"{ba.acc_number or ''} - {ba.bank_id.name}" if ba.bank_id else (ba.acc_number or bank_name)
                if journal and journal.default_account_id:
                    account_number = journal.default_account_id.code or ""
                new_line_vals.append({
                    "journal_id": journal.id if journal else False,
                    "bank_name": bank_name,
                    "account_number": account_number,
                    "reference": dc.name or dc.description or "",
                    "date": dc.date,
                    "amount": dc.total or 0.0,
                })
        except KeyError:
            pass

        # bank.transfer (transferencias banco a banco)
        try:
            BankTransfer = self.env["bank.transfer"]
            bt_domain = [
                ("state", "=", "validated"),
                ("date", "=", report_date),
            ]
            if branch_id:
                bt_domain.append(("branch_id", "=", branch_id))
            transfers = BankTransfer.search(bt_domain, order="name")
            for bt in transfers:
                dest_journal = bt.dest_journal_id
                account_number = ""
                bank_name = dest_journal.name if dest_journal else bt.name or _("Transferencia")
                if dest_journal and hasattr(dest_journal, "bank_account_id") and dest_journal.bank_account_id:
                    ba = dest_journal.bank_account_id
                    bank_name = f"{ba.acc_number or ''} - {ba.bank_id.name}" if ba.bank_id else (ba.acc_number or bank_name)
                if dest_journal and dest_journal.default_account_id:
                    account_number = dest_journal.default_account_id.code or ""
                new_line_vals.append({
                    "journal_id": dest_journal.id if dest_journal else False,
                    "bank_name": bank_name,
                    "account_number": account_number,
                    "reference": bt.name or bt.description or "",
                    "date": bt.date,
                    "amount": bt.total or 0.0,
                })
        except KeyError:
            pass

        if new_line_vals:
            next_seq = max((l.sequence or 10 for l in self.remesa_line_ids), default=10) + 1
            for i, vals in enumerate(new_line_vals):
                vals["sequence"] = next_seq + i
            self.write({
                "remesa_line_ids": [(0, 0, v) for v in new_line_vals],
            })
        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Sin remesas"),
                    "message": _("No se encontraron depósitos ni transferencias del día para esta sucursal."),
                    "type": "warning",
                    "sticky": False,
                },
            }

    def action_generate_move(self):
        """Abre el wizard para generar el asiento de depósito de efectivo y anticipos."""
        self.ensure_one()
        if self.state != "done":
            raise UserError(
                _("Solo puede generar asiento cuando el cierre está Finalizado.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Generar Asiento de Cierre"),
            "res_model": "gn.cash.closing.generate.move.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }

    def action_print_xlsx(self):
        """Genera el reporte Excel del cierre de caja (botón Cierre XLS)."""
        self.ensure_one()
        if self.state == "cancel":
            raise UserError(_("No puede imprimir un cierre anulado."))
        if not self.env.user.has_group(
            "gn_daily_cash_closing.group_cash_closing_generate"
        ):
            raise ValidationError(
                _("No tiene permiso para generar el reporte de Cierre de Caja.")
            )
        return self.env.ref(
            "gn_daily_cash_closing.action_cash_closing_report_xlsx"
        ).report_action(self)

    def action_print_closing(self):
        """Genera el reporte PDF del cierre de caja (botón Cierre PDF)."""
        self.ensure_one()
        if self.state == "cancel":
            raise UserError(_("No puede imprimir un cierre anulado."))
        return self.export_pdf()

    def export_pdf(self):
        """Genera el reporte PDF del cierre de caja."""
        self.ensure_one()
        if not self.env.user.has_group(
            "gn_daily_cash_closing.group_cash_closing_generate"
        ):
            raise ValidationError(
                _("No tiene permiso para generar el reporte de Cierre de Caja.")
            )
        data = {
            "date": str(self.date),
            "branch_id": self.branch_id.id,
            "branch_name": self.branch_id.name,
            "user_id": self.user_id.id if self.user_id else False,
            "user_name": self.user_id.name if self.user_id else "",
            "closing_id": self.id,
            "observaciones": self.observaciones or "",
            "remesas": [
                {
                    "bank_name": r.bank_name or "",
                    "account_number": r.account_number or "",
                    "reference": r.reference or "",
                    "date": str(r.date) if r.date else "",
                    "amount": r.amount,
                }
                for r in self.remesa_line_ids
            ],
            "remesas_sobrantes": sum(self.remesa_sobrante_line_ids.mapped("amount") or [0]),
        }
        return self.env.ref(
            "gn_daily_cash_closing.action_cash_closing_report_persistent"
        ).report_action(self, data=data)
