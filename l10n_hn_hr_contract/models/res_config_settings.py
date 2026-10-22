# © 2025 Grupo Nahuiik

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hr_contract_work_days_per_year = fields.Float(
        related="company_id.hr_contract_work_days_per_year",
        readonly=False,
    )
    hr_contract_timeoff_auto_allocation = fields.Boolean(
        related="company_id.hr_contract_timeoff_auto_allocation",
        readonly=False,
    )
    hr_contract_timeoff_auto_allocation_type_id = fields.Many2one(
        "hr.leave.type",
        related="company_id.hr_contract_timeoff_auto_allocation_type_id",
        readonly=False,
    )



