from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    purchase_order_number = fields.Char(string="Orden de Compra")
    add_invoice_attachment = fields.Boolean(string="Adjuntar Documento")
    purchase_order_attachment = fields.Binary(
        string="Archivo Orden de Compra", attachment=True
    )
