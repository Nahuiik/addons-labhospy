# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleReceiptInvoiceAssignWizard(models.TransientModel):
    _name = "sale.receipt.invoice.assign.wizard"
    _description = "Asignar facturas a recibo"

    receipt_id = fields.Many2one("sale.receipt", string="Recibo", required=True)
    line_ids = fields.One2many("sale.receipt.invoice.assign.line", "wizard_id", string="Facturas")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        receipt = self.env["sale.receipt"].browse(self.env.context.get("default_receipt_id"))
        if receipt and "line_ids" in fields_list:
            lines = []
            domain = [
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "=", "posted"),
                ("partner_id", "=", receipt.partner_id.id),
                ("amount_residual", ">", 0),
            ]
            invoices = self.env["account.move"].search(domain)
            for inv in invoices:
                lines.append((0, 0, {
                    "invoice_id": inv.id,
                    "residual": inv.amount_residual,
                    "assigned_amount": 0.0,
                }))
            res["line_ids"] = lines
        return res

    def action_apply(self):
        self.ensure_one()
        receipt = self.receipt_id
        assigned_lines = []
        for line in self.line_ids:
            if line.assigned_amount:
                assigned_lines.append((0, 0, {
                    "invoice_id": line.invoice_id.id,
                    "assigned_amount": line.assigned_amount,
                }))
        if assigned_lines:
            receipt.write({"invoice_line_ids": [(5, 0, 0)] + assigned_lines})
        return {"type": "ir.actions.act_window_close"}


class SaleReceiptInvoiceAssignLine(models.TransientModel):
    _name = "sale.receipt.invoice.assign.line"
    _description = "Líneas wizard asignación"

    wizard_id = fields.Many2one("sale.receipt.invoice.assign.wizard", required=True)
    invoice_id = fields.Many2one("account.move", string="Factura", required=True)
    residual = fields.Monetary(string="Saldo", currency_field="currency_id", readonly=True)
    assigned_amount = fields.Monetary(string="Importe a asignar")
    currency_id = fields.Many2one(related="invoice_id.currency_id", store=False)
