from odoo import api, fields, models


class DynamicReportLine(models.Model):
    _name = "dynamic.report.line"
    _description = "Dynamic Report Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=0)
    report_id = fields.Many2one("dynamic.report", required=True, ondelete="cascade")
    document_name = fields.Char()
    document_date = fields.Date()
    partner_id = fields.Many2one("res.partner")
    partner_name = fields.Char()
    product_id = fields.Many2one("product.product")
    product_name = fields.Char()
    category_name = fields.Char()
    salesperson_name = fields.Char()
    quantity = fields.Float(digits="Product Unit of Measure")
    price_unit = fields.Float(digits="Product Price")
    subtotal = fields.Monetary(currency_field="currency_id")
    tax_amount = fields.Monetary(currency_field="currency_id")
    total = fields.Monetary(currency_field="currency_id")
    status_label = fields.Char(string="Status")
    invoice_state_label = fields.Char(string="Invoice State")
    taxable_amount = fields.Monetary(currency_field="currency_id")
    exempt_amount = fields.Monetary(currency_field="currency_id")
    discount_amount = fields.Monetary(currency_field="currency_id")
    cost_unit = fields.Monetary(currency_field="currency_id")
    cost_total = fields.Monetary(currency_field="currency_id")
    margin_amount = fields.Monetary(currency_field="currency_id")
    margin_percent = fields.Float()
    currency_id = fields.Many2one("res.currency")
    company_id = fields.Many2one("res.company", related="report_id.company_id", store=True, readonly=True)
    extra_json = fields.Json(string="Extra data", help="Stores any additional columns needed for the report.")

    @api.model_create_multi
    def create(self, vals_list):
        for index, vals in enumerate(vals_list, start=1):
            vals.setdefault("sequence", index)
        return super().create(vals_list)
