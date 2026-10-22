# -*- coding: utf-8 -*-
from odoo import api, models


class ReportPayslip(models.AbstractModel):
    _name = "report.l10n_hn_payroll_base.report_payslip"
    _description = "Payslip PDF"

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            "doc_ids": docids,
            "docs": self.env["hr.payslip"].browse(docids),
        }
