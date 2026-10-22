from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    hn_employee_costs_hour = fields.Monetary(
        string="Costo mano de obra / hora",
        currency_field="currency_id",
        help="Costo adicional de mano de obra por hora para esta operación, "
        "sumado al costo del centro de trabajo en la vista general de la OP.",
    )
