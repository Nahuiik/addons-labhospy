# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class GnCashClosingBlindWizard(models.TransientModel):
    _name = "gn.cash.closing.blind.wizard"
    _description = "Wizard Cierre Inicial a Ciegas"

    state = fields.Selection(
        [
            ("inicio", "Inicio"),
            ("digitando", "Digitando"),
            ("comparacion", "Comparación"),
        ],
        string="Paso",
        default="inicio",
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        default=lambda self: self.env.user,
        readonly=True,
    )
    date = fields.Date(string="Día", required=True, default=fields.Date.context_today)
    branch_id = fields.Many2one(
        "res.branch", string="Sucursal", required=True,
    )
    data_loaded = fields.Boolean(
        string="Datos cargados",
        default=False,
        help="True después de Iniciar Cierre",
    )
    # Montos digitados por el usuario
    efectivo_digitado = fields.Float(string="Efectivo (digitado)", digits=(16, 2))
    tarjetas_digitado = fields.Float(string="Tarjetas (digitado)", digits=(16, 2))
    transferencias_digitado = fields.Float(string="Transferencias (digitado)", digits=(16, 2))
    # Valores calculados del sistema
    efectivo_calculado = fields.Float(
        string="Efectivo (calculado)",
        compute="_compute_ingresos",
        digits=(16, 2),
    )
    tarjetas_calculado = fields.Float(
        string="Tarjetas (calculado)",
        compute="_compute_ingresos",
        digits=(16, 2),
    )
    transferencias_calculado = fields.Float(
        string="Transferencias (calculado)",
        compute="_compute_ingresos",
        digits=(16, 2),
    )
    # Diferencias (digitado - calculado)
    efectivo_diferencia = fields.Float(
        string="Diferencia Efectivo",
        compute="_compute_diferencias",
        digits=(16, 2),
    )
    tarjetas_diferencia = fields.Float(
        string="Diferencia Tarjetas",
        compute="_compute_diferencias",
        digits=(16, 2),
    )
    transferencias_diferencia = fields.Float(
        string="Diferencia Transferencias",
        compute="_compute_diferencias",
        digits=(16, 2),
    )
    # Helpers para decoración (rojo cuando falta)
    efectivo_falta = fields.Boolean(
        compute="_compute_diferencias",
        help="True si efectivo digitado < calculado",
    )
    tarjetas_falta = fields.Boolean(compute="_compute_diferencias")
    transferencias_falta = fields.Boolean(compute="_compute_diferencias")

    can_edit_branch = fields.Boolean(
        compute="_compute_can_edit_branch",
        help="True si el usuario tiene permiso de supervisor",
    )
    total_facturas = fields.Integer(
        string="Total facturas",
        compute="_compute_total_facturas",
    )
    total_facturas_monto = fields.Float(
        string="Monto total facturas",
        compute="_compute_total_facturas",
        digits=(16, 2),
    )
    closing_notes = fields.Text(string="Nota de cierre")
    closing_id = fields.Many2one(
        "gn.cash.closing",
        string="Cierre generado",
        readonly=True,
    )

    @api.depends("date", "branch_id")
    def _compute_total_facturas(self):
        for wiz in self:
            if not wiz.date or not wiz.branch_id:
                wiz.total_facturas = 0
                wiz.total_facturas_monto = 0.0
                continue
            domain = [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("branch_id", "=", wiz.branch_id.id),
            ]
            invoices = self.env["account.move"].search(domain).filtered(
                lambda m: (m.invoice_date or m.date) == wiz.date
            )
            wiz.total_facturas = len(invoices)
            wiz.total_facturas_monto = sum(
                abs(inv.amount_total_signed or 0) for inv in invoices
            )

    @api.depends()
    def _compute_can_edit_branch(self):
        for wiz in self:
            wiz.can_edit_branch = self.env.user.has_group(
                "gn_daily_cash_closing.group_cash_closing_supervisor"
            )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if "user_id" in fields_list and not vals.get("user_id"):
            vals["user_id"] = self.env.user.id
        if "branch_id" in fields_list and not vals.get("branch_id"):
            vals["branch_id"] = self.env.user.branch_id.id
        return vals

    @api.depends("date", "branch_id", "data_loaded")
    def _compute_ingresos(self):
        report = self.env["report.gn_daily_cash_closing.cash_closing_template"]
        for wiz in self:
            if not wiz.data_loaded or not wiz.date or not wiz.branch_id:
                wiz.efectivo_calculado = wiz.tarjetas_calculado = wiz.transferencias_calculado = 0.0
                continue
            ingresos = report._get_ingresos(wiz.date, wiz.branch_id.id)
            wiz.efectivo_calculado = ingresos.get("efectivo", 0) or 0
            wiz.tarjetas_calculado = ingresos.get("tarjeta", 0) or 0
            wiz.transferencias_calculado = ingresos.get("transferencia", 0) or 0

    @api.depends(
        "efectivo_digitado", "tarjetas_digitado", "transferencias_digitado",
        "efectivo_calculado", "tarjetas_calculado", "transferencias_calculado",
    )
    def _compute_diferencias(self):
        for wiz in self:
            wiz.efectivo_diferencia = (wiz.efectivo_digitado or 0) - (wiz.efectivo_calculado or 0)
            wiz.tarjetas_diferencia = (wiz.tarjetas_digitado or 0) - (wiz.tarjetas_calculado or 0)
            wiz.transferencias_diferencia = (
                (wiz.transferencias_digitado or 0) - (wiz.transferencias_calculado or 0)
            )
            wiz.efectivo_falta = wiz.efectivo_diferencia < 0
            wiz.tarjetas_falta = wiz.tarjetas_diferencia < 0
            wiz.transferencias_falta = wiz.transferencias_diferencia < 0

    def action_iniciar_cierre(self):
        """Paso 1 -> 2: Inicia el cierre, carga datos calculados."""
        self.ensure_one()
        if not self.date or not self.branch_id:
            raise ValidationError(
                _("Debe seleccionar fecha y sucursal antes de iniciar el cierre.")
            )
        self.data_loaded = True
        self.state = "digitando"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_continuar(self):
        """Paso 2 -> 3: Valida montos, crea el cierre (tras confirmación del usuario) y pasa a comparación."""
        self.ensure_one()
        if (self.efectivo_digitado or 0) == 0 and (self.tarjetas_digitado or 0) == 0 and (self.transferencias_digitado or 0) == 0:
            raise ValidationError(
                _("Debe digitar al menos un monto en Efectivo, Liquidación Tarjeta o Transferencias.")
            )
        if not self.env.user.has_group("gn_daily_cash_closing.group_cash_closing_generate"):
            raise UserError(_("No tiene permiso para crear cierres de caja."))

        # Crear cierre en background (sin mostrarlo)
        closing = self.env["gn.cash.closing"].create({
            "date": self.date,
            "branch_id": self.branch_id.id,
            "observaciones": self.closing_notes or "",
            "cierre_inicial_efectivo": self.efectivo_digitado or 0,
            "cierre_inicial_tarjeta": self.tarjetas_digitado or 0,
            "cierre_inicial_transferencia": self.transferencias_digitado or 0,
        })
        closing.action_load_data()
        self.closing_id = closing

        branch_id = self.branch_id.id
        branch_name = self.branch_id.name or ""
        remesa_vals = []

        if self.efectivo_diferencia > 0:
            journal = self._get_journal_efectivo(branch_id)
            remesa_vals.append({
                "closing_id": closing.id,
                "journal_id": journal.id if journal else False,
                "reference": f"CORTE DE CAJA {branch_name} - Sobrante efectivo".strip(),
                "date": self.date,
                "amount": self.efectivo_diferencia,
            })
        if self.tarjetas_diferencia > 0:
            journal = self._get_journal_tarjeta(branch_id)
            if not journal:
                journal = self._get_journal_efectivo(branch_id)
            remesa_vals.append({
                "closing_id": closing.id,
                "journal_id": journal.id if journal else False,
                "reference": f"CORTE DE CAJA {branch_name} - Sobrante tarjetas".strip(),
                "date": self.date,
                "amount": self.tarjetas_diferencia,
            })
        if self.transferencias_diferencia > 0:
            journal = self._get_journal_transferencia(branch_id)
            if not journal:
                journal = self._get_journal_efectivo(branch_id)
            remesa_vals.append({
                "closing_id": closing.id,
                "journal_id": journal.id if journal else False,
                "reference": f"CORTE DE CAJA {branch_name} - Sobrante transferencia".strip(),
                "date": self.date,
                "amount": self.transferencias_diferencia,
            })

        if remesa_vals:
            self.env["gn.cash.closing.remesa.sobrante.line"].create(remesa_vals)

        self.state = "comparacion"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def _get_journal_efectivo(self, branch_id):
        """Primer diario efectivo de la sucursal."""
        Journal = self.env["account.journal"]
        domain = [
            ("type", "=", "cash"),
            "|",
            ("branch_id", "=", False),
            ("branch_id", "=", branch_id),
        ]
        return Journal.search(domain, limit=1)

    def _get_journal_tarjeta(self, branch_id):
        """Primer diario tarjeta de la sucursal."""
        Journal = self.env["account.journal"]
        if "payment_mode" in Journal._fields:
            domain = [
                ("payment_mode", "=", "tarjeta"),
                "|",
                ("branch_id", "=", False),
                ("branch_id", "=", branch_id),
            ]
            return Journal.search(domain, limit=1)
        if "is_credit_card" in Journal._fields:
            domain = [
                ("type", "=", "bank"),
                ("is_credit_card", "=", True),
                "|",
                ("branch_id", "=", False),
                ("branch_id", "=", branch_id),
            ]
            return Journal.search(domain, limit=1)
        return Journal.browse([])

    def _get_journal_transferencia(self, branch_id):
        """Primer diario transferencia de la sucursal."""
        Journal = self.env["account.journal"]
        if "payment_mode" in Journal._fields:
            domain = [
                ("payment_mode", "=", "transferencia"),
                "|",
                ("branch_id", "=", False),
                ("branch_id", "=", branch_id),
            ]
            return Journal.search(domain, limit=1)
        domain = [
            ("type", "=", "bank"),
            "|",
            ("branch_id", "=", False),
            ("branch_id", "=", branch_id),
        ]
        return Journal.search(domain, limit=1)

    def action_descargar_cierre(self):
        """Descarga el PDF del cierre de caja (Venta Diaria)."""
        self.ensure_one()
        if self.state != "comparacion":
            raise ValidationError(_("Debe completar los pasos anteriores."))
        if not self.closing_id:
            raise ValidationError(_("No hay cierre generado para descargar."))
        return self.closing_id.export_pdf()

    def action_imprimir_voucher(self):
        """Imprime el voucher del cierre a ciegas."""
        self.ensure_one()
        if self.state != "comparacion":
            raise ValidationError(_("Debe completar los pasos anteriores."))
        return self.env.ref(
            "gn_daily_cash_closing.action_blind_closing_voucher"
        ).report_action(docids=[self.id])

    def action_finalizar(self):
        """Cierra el wizard."""
        self.ensure_one()
        if self.state != "comparacion":
            raise ValidationError(_("Debe completar los pasos anteriores."))
        return {"type": "ir.actions.act_window_close"}
