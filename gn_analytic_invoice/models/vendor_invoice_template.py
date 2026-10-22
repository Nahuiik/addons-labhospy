from odoo import api, fields, models


class VendorInvoiceTemplate(models.Model):
    _name = "vendor.invoice.template"
    _description = "Plantilla de Factura de Proveedor"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        domain=[("supplier_rank", ">", 0)],
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        domain=[("type", "=", "purchase")],
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    analytic_distribution = fields.Json("Distribución Analítica por Defecto")
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
    line_ids = fields.One2many(
        "vendor.invoice.template.line",
        "template_id",
        string="Líneas",
        copy=True,
    )

    @api.onchange("analytic_dist_template_id")
    def _onchange_analytic_dist_template_id(self):
        if self.analytic_dist_template_id:
            self.analytic_distribution = (
                self.analytic_dist_template_id.analytic_distribution
            )
