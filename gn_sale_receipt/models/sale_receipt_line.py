# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleReceiptLine(models.Model):
    _name = "sale.receipt.line"
    _description = "Sale Receipt Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    receipt_id = fields.Many2one("sale.receipt", string="Recibo", ondelete="cascade")
    company_id = fields.Many2one(related="receipt_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="receipt_id.currency_id", store=True, readonly=True)

    product_id = fields.Many2one(
        "product.product", 
        string="Producto",
        domain="[('type', '=', 'service'), ('for_sale_receipt', '=', True)]",
    )
    name = fields.Char(string="Descripción")
    account_id = fields.Many2one("account.account", string="Cuenta")
    analytic_account_id = fields.Many2one("account.analytic.account", string="Cuenta analítica")
    quantity = fields.Float(string="Cantidad", default=1.0)
    price_unit = fields.Monetary(string="Precio unitario")
    tax_ids = fields.Many2many(
        "account.tax",
        string="Impuestos",
        domain="[('type_tax_use', '=', 'sale')]",
    )

    price_subtotal = fields.Monetary(string="Subtotal", compute="_compute_amount", store=True, currency_field="currency_id")
    price_tax = fields.Monetary(string="Impuesto", compute="_compute_amount", store=True, currency_field="currency_id")

    @api.model_create_multi
    def create(self, vals_list):
        """Prevenir crear líneas si el recibo está publicado"""
        for vals in vals_list:
            if vals.get('receipt_id'):
                receipt = self.env['sale.receipt'].browse(vals['receipt_id'])
                if receipt.state != 'draft':
                    raise ValidationError(_("No se pueden agregar líneas a un recibo que ya está publicado o cancelado."))
        return super().create(vals_list)

    def write(self, vals):
        """Prevenir modificar líneas si el recibo está publicado"""
        for line in self:
            if line.receipt_id.state != 'draft':
                raise ValidationError(_("No se pueden modificar líneas de un recibo que ya está publicado o cancelado."))
        return super().write(vals)

    def unlink(self):
        """Prevenir eliminar líneas si el recibo está publicado"""
        for line in self:
            if line.receipt_id.state != 'draft':
                raise ValidationError(_("No se pueden eliminar líneas de un recibo que ya está publicado o cancelado."))
        return super().unlink()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Heredar precio de venta, impuestos y cuenta contable del producto"""
        if not self.product_id:
            return
        
        product = self.product_id
        
        # Heredar precio de venta
        if product.list_price:
            self.price_unit = product.list_price
        
        # Heredar impuestos de venta
        if product.taxes_id:
            # Filtrar solo impuestos de tipo venta
            sale_taxes = product.taxes_id.filtered(lambda t: t.type_tax_use == 'sale')
            if sale_taxes:
                self.tax_ids = sale_taxes
        
        # Heredar descripción del producto
        if product.display_name and not self.name:
            self.name = product.display_name
        
        # Obtener cuenta contable de gasto
        # Prioridad: 1. Cuenta de gasto del producto, 2. Cuenta de gasto de la categoría
        account = False
        if product.property_account_expense_id:
            account = product.property_account_expense_id
        elif product.categ_id and product.categ_id.property_account_expense_categ_id:
            account = product.categ_id.property_account_expense_categ_id
        
        if account:
            self.account_id = account

    @api.depends("quantity", "price_unit", "tax_ids", "currency_id")
    def _compute_amount(self):
        for line in self:
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                currency=line.currency_id,
                quantity=line.quantity,
            ) if line.tax_ids else False
            if taxes:
                line.price_subtotal = taxes["total_excluded"]
                line.price_tax = sum(t.get("amount", 0.0) for t in taxes.get("taxes", []))
            else:
                line.price_subtotal = line.quantity * line.price_unit
                line.price_tax = 0.0
