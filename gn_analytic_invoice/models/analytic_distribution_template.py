from odoo import fields, models


class AnalyticDistributionTemplate(models.Model):
    _name = "analytic.distribution.template"
    _description = "Plantilla de Distribución Analítica"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    analytic_distribution = fields.Json("Distribución Analítica")
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        ),
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
