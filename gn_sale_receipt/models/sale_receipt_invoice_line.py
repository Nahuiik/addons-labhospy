# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleReceiptInvoiceLine(models.Model):
    _name = "sale.receipt.invoice.line"
    _description = "Sale Receipt Invoice Line"
    _order = "invoice_id"

    receipt_id = fields.Many2one("sale.receipt", string="Recibo", ondelete="cascade", required=True)
    company_id = fields.Many2one(related="receipt_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="receipt_id.currency_id", store=True, readonly=True)

    invoice_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        domain="[('move_type','in',('out_invoice','out_refund'))]",
    )
    assigned_amount = fields.Monetary(string="Importe asignado", required=True)

    invoice_amount_total = fields.Monetary(related="invoice_id.amount_total", string="Total factura", store=False)
    invoice_residual = fields.Monetary(related="invoice_id.amount_residual", string="Residual", store=False)

    @api.model_create_multi
    def create(self, vals_list):
        """Prevenir crear líneas si el recibo está publicado"""
        for vals in vals_list:
            if vals.get('receipt_id'):
                receipt = self.env['sale.receipt'].browse(vals['receipt_id'])
                if receipt.state != 'draft':
                    raise ValidationError(_("No se pueden agregar facturas a un recibo que ya está publicado o cancelado."))
        return super().create(vals_list)

    def write(self, vals):
        """Prevenir modificar líneas si el recibo está publicado"""
        for line in self:
            if line.receipt_id.state != 'draft':
                raise ValidationError(_("No se pueden modificar facturas de un recibo que ya está publicado o cancelado."))
        return super().write(vals)

    def unlink(self):
        """Prevenir eliminar líneas si el recibo está publicado"""
        for line in self:
            if line.receipt_id.state != 'draft':
                raise ValidationError(_("No se pueden eliminar facturas de un recibo que ya está publicado o cancelado."))
        return super().unlink()

    @api.constrains("assigned_amount")
    def _check_assigned_amount(self):
        for line in self:
            if line.assigned_amount < 0:
                raise ValidationError(_("El importe asignado debe ser positivo."))
