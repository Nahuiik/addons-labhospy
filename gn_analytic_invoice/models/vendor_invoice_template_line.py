from odoo import api, fields, models


class VendorInvoiceTemplateLine(models.Model):
    _name = "vendor.invoice.template.line"
    _description = "Línea de Plantilla de Factura de Proveedor"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "vendor.invoice.template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", string="Producto")
    name = fields.Char(string="Descripción")
    account_id = fields.Many2one(
        "account.account",
        string="Cuenta",
        domain=[
            ("account_type", "not in", ("asset_receivable", "liability_payable", "off_balance")),
        ],
    )
    quantity = fields.Float(string="Cantidad", default=1.0)
    price_unit = fields.Float(string="Precio Unitario")
    tax_ids = fields.Many2many(
        "account.tax",
        string="Impuestos",
        domain=[("type_tax_use", "=", "purchase")],
    )
    analytic_distribution = fields.Json("Distribución Analítica")
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        ),
    )
    analytic_dist_template_id = fields.Many2one(
        "analytic.distribution.template",
        string="Plantilla de Distribución",
        ondelete="set null",
    )

    @api.onchange("analytic_dist_template_id")
    def _onchange_analytic_dist_template_id(self):
        if self.analytic_dist_template_id:
            self.analytic_distribution = (
                self.analytic_dist_template_id.analytic_distribution
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if not self.product_id:
            return
        product = self.product_id
        if not self.name:
            self.name = product.display_name
        if not self.account_id:
            accounts = product.product_tmpl_id.get_product_accounts()
            self.account_id = accounts.get("expense", False)
        if not self.price_unit:
            self.price_unit = product.standard_price
        if not self.tax_ids:
            self.tax_ids = product.supplier_taxes_id
