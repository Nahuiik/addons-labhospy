# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sales_dashboard_config_id = fields.Many2one(
        'sales.dashboard.config',
        string='Config. dashboard ventas',
        compute='_compute_sales_dashboard_config',
    )

    def _compute_sales_dashboard_config(self):
        Config = self.env['sales.dashboard.config']
        for company in self:
            company.sales_dashboard_config_id = Config.get_for_company(company)
