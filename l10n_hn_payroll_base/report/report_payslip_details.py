# -*- coding: utf-8 -*-
from odoo import api, models


class PayslipDetailsReport(models.AbstractModel):
    _name = "report.l10n_hn_payroll_base.report_payslipdetails"
    _description = "Payslip lines grouped for PDF"

    def _details_by_rule_category(self, payslip_lines):
        grouped = {}
        for line in payslip_lines:
            grouped.setdefault(line.slip_id.id, {})
            grouped[line.slip_id.id].setdefault(line.category_id, self.env["hr.payslip.line"])
            grouped[line.slip_id.id][line.category_id] |= line
        result = {}
        for slip_id, categ_map in grouped.items():
            result[slip_id] = []
            for categ, lines in categ_map.items():
                result[slip_id].append(
                    {
                        "rule_category": categ.name,
                        "level": 0,
                        "total": sum(lines.mapped("total")),
                        "lines": lines.filtered("appears_on_payslip"),
                    }
                )
        return result

    @api.model
    def _get_report_values(self, docids, data=None):
        payslips = self.env["hr.payslip"].browse(docids)
        lines = payslips.mapped("line_ids").filtered(lambda l: l.appears_on_payslip)
        return {
            "doc_ids": docids,
            "docs": payslips,
            "lines_by_category": self._details_by_rule_category(lines),
        }
