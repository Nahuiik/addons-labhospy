# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class Filter(models.Model):
    # Added field to store filter value for stock movement report filter data
    _inherit = "ir.filters"

    filter_options = fields.Char(string="Report Filter", store=True)


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.depends("name", "parent_id.name")
    def _compute_display_name(self):
        for company in self:
            if company.parent_id:
                company.display_name = f"{company.name} [{company.parent_id.name}]"
            else:
                company.display_name = company.name


class ResUsers(models.Model):
    _inherit = "res.users"

    def get_companies(self):
        return self.env.companies.ids