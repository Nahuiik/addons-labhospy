# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CashClosingWizard(models.TransientModel):
    _name = "gn.cash.closing.wizard"
    _description = "Wizard Cierre de Caja Diario"

    date = fields.Date(
        string="Día", required=True, default=fields.Date.context_today,
    )
    branch_id = fields.Many2one(
        "res.branch", string="Sucursal", required=True,
    )
    observaciones = fields.Text(string="Observaciones")
    data_loaded = fields.Boolean(
        string="Datos cargados",
        default=False,
        help="True después de hacer clic en Obtener datos",
    )
    remesa_line_ids = fields.One2many(
        "gn.cash.closing.wizard.remesa.line", "wizard_id",
        string="Remesas Bancarias",
    )
    # Pestañas de datos (solo lectura)
    invoice_open_ids = fields.Many2many(
        "account.move", compute="_compute_tab_data",
        string="Facturas Abiertas", readonly=True,
    )
    invoice_paid_ids = fields.Many2many(
        "account.move", compute="_compute_tab_data",
        string="Facturas Pagadas", readonly=True,
    )
    invoice_cancelled_ids = fields.Many2many(
        "account.move", compute="_compute_tab_data",
        string="Facturas Anuladas", readonly=True,
    )
    payment_posted_ids = fields.Many2many(
        "account.payment", compute="_compute_tab_data",
        string="Pagos Realizados", readonly=True,
    )
    payment_cancelled_ids = fields.Many2many(
        "account.payment", compute="_compute_tab_data",
        string="Pagos Anulados", readonly=True,
    )
    advance_ids = fields.Many2many(
        "account.payment", compute="_compute_tab_data",
        string="Anticipos", readonly=True,
    )
    advance_presupuesto_ids = fields.Many2many(
        "account.payment", compute="_compute_tab_data",
        string="Anticipos (Cotización Presupuesto)", readonly=True,
    )
    advance_prefactura_ids = fields.Many2many(
        "account.payment", compute="_compute_tab_data",
        string="Anticipos Pre-Factura", readonly=True,
    )
    can_edit_branch = fields.Boolean(
        compute="_compute_can_edit_branch",
        help="True si el usuario tiene permiso de supervisor para ver todas las sucursales",
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
        if "branch_id" in fields_list and not vals.get("branch_id"):
            vals["branch_id"] = self.env.user.branch_id.id
        return vals

    @api.depends("date", "branch_id", "data_loaded")
    def _compute_tab_data(self):
        Move = self.env["account.move"]
        Payment = self.env["account.payment"]
        for wiz in self:
            if not wiz.data_loaded or not wiz.date or not wiz.branch_id:
                wiz.invoice_open_ids = Move
                wiz.invoice_paid_ids = Move
                wiz.invoice_cancelled_ids = Move
                wiz.payment_posted_ids = Payment
                wiz.payment_cancelled_ids = Payment
                wiz.advance_ids = Payment
                wiz.advance_presupuesto_ids = Payment
                wiz.advance_prefactura_ids = Payment
                continue
            branch_id = wiz.branch_id.id
            report_date = wiz.date

            # Facturas abiertas: posted, no pagadas
            inv_open = Move.search([
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "!=", "paid"),
                ("branch_id", "=", branch_id),
            ])
            inv_open = inv_open.filtered(
                lambda m: (m.invoice_date or m.date) == report_date
            )
            wiz.invoice_open_ids = inv_open

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
            wiz.invoice_paid_ids = inv_paid

            # Facturas anuladas
            inv_cancelled = Move.search([
                ("move_type", "=", "out_invoice"),
                ("state", "=", "cancel"),
                ("branch_id", "=", branch_id),
            ])
            inv_cancelled = inv_cancelled.filtered(
                lambda m: (m.invoice_date or m.date) == report_date
            )
            wiz.invoice_cancelled_ids = inv_cancelled

            # Pagos realizados (posted)
            pay_posted = Payment.search([
                ("payment_type", "=", "inbound"),
                ("state", "in", ["in_process", "paid"]),
                ("date", "=", report_date),
                ("branch_id", "=", branch_id),
            ])
            wiz.payment_posted_ids = pay_posted

            # Pagos anulados
            pay_cancelled = Payment.search([
                ("payment_type", "=", "inbound"),
                ("state", "=", "canceled"),
                ("date", "=", report_date),
                ("branch_id", "=", branch_id),
            ])
            wiz.payment_cancelled_ids = pay_cancelled

            # Anticipos: separar por estado de cotización vinculada
            if "is_advance" in Payment._fields:
                advances = Payment.search([
                    ("payment_type", "=", "inbound"),
                    ("is_advance", "=", True),
                    ("state", "in", ["in_process", "paid"]),
                    ("date", "=", report_date),
                    ("branch_id", "=", branch_id),
                ])
                wiz.advance_ids = advances
                presupuesto = Payment.browse([])
                prefactura = Payment.browse([])
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
                wiz.advance_presupuesto_ids = presupuesto
                wiz.advance_prefactura_ids = prefactura
            else:
                wiz.advance_ids = Payment
                wiz.advance_presupuesto_ids = Payment
                wiz.advance_prefactura_ids = Payment

    def action_load_data(self):
        """Marca data_loaded=True para disparar el compute de las pestañas."""
        self.ensure_one()
        if not self.date or not self.branch_id:
            raise ValidationError(
                _("Debe seleccionar fecha y sucursal antes de obtener los datos.")
            )
        self.data_loaded = True

    def export_pdf(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "gn_daily_cash_closing.group_cash_closing_generate"
        ):
            raise ValidationError(
                _("No tiene permiso para generar el reporte de Cierre de Caja.")
            )
        if not self.data_loaded:
            raise ValidationError(
                _("Debe hacer clic en 'Obtener datos' antes de generar el reporte.")
            )
        data = {
            "date": str(self.date),
            "branch_id": self.branch_id.id,
            "branch_name": self.branch_id.name,
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
        }
        return self.env.ref(
            "gn_daily_cash_closing.action_cash_closing_report"
        ).report_action(self, data=data)


class CashClosingWizardRemesaLine(models.TransientModel):
    _name = "gn.cash.closing.wizard.remesa.line"
    _description = "Línea de Remesa Bancaria (Wizard)"

    wizard_id = fields.Many2one(
        "gn.cash.closing.wizard", string="Wizard", ondelete="cascade",
    )
    bank_name = fields.Char(string="Banco", required=True)
    account_number = fields.Char(string="No. Cuenta")
    reference = fields.Char(string="Referencia")
    date = fields.Date(string="Fecha")
    amount = fields.Float(string="Monto", digits=(16, 2))
