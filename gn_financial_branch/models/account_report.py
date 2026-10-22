# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.fields import Domain


class AccountReport(models.Model):
    _inherit = "account.report"

    filter_res_branch = fields.Boolean(
        string="Branches",
        compute=lambda r: r._compute_report_option_filter("filter_res_branch"),
        readonly=False,
        precompute=True,
        store=True,
        depends=["root_report_id", "section_main_report_ids"],
    )

    def _init_options_res_branch(self, options, previous_options):
        if not self.filter_res_branch:
            return

        options["res_branch"] = True
        previous_ids = previous_options.get("res_branch_ids") or []
        selected_ids = [int(x) for x in previous_ids]
        Branch = self.env["res.branch"].with_context(active_test=False)
        selected = (
            Branch.search([("id", "in", selected_ids)]) if selected_ids else Branch.browse()
        )
        company_ids = set(self.get_report_company_ids(options))
        selected = selected.filtered(lambda b: b.company_id.id in company_ids)
        options["res_branch_ids"] = selected.ids
        options["selected_res_branch_names"] = selected.mapped("name")

    def _get_options_res_branch_domain(self, options):
        if not self.filter_res_branch:
            return Domain.TRUE
        ids = options.get("res_branch_ids") or []
        if not ids:
            return Domain.TRUE
        return Domain("branch_id", "in", ids)

    def _get_options_domain(self, options, date_scope):
        domain = super()._get_options_domain(options, date_scope)
        return domain & self._get_options_res_branch_domain(options)

    def _get_options_initializers_forced_sequence_map(self):
        res = super()._get_options_initializers_forced_sequence_map()
        return {**res, self._init_options_res_branch: 201}
