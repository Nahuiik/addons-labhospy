# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ReportExecutiveSummary(models.AbstractModel):
    _name = "report.bi_financial_reports_comm.executive_summary_pdf_report"
    _description = "Executive Summary PDF Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        doc = data or {}
        return {"doc": doc}
