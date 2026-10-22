# -*- coding: utf-8 -*-
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ContributionRegisterReport(models.AbstractModel):
    _name = "report.l10n_hn_payroll_base.report_contributionregister"
    _description = "Contribution register PDF"

    def _get_payslip_lines(self, register_ids, date_from, date_to):
        if not register_ids:
            return {}
        result = {rid: self.env["hr.payslip.line"] for rid in register_ids}
        lines = self.env["hr.payslip.line"].search(
            [
                ("register_id", "in", list(register_ids)),
                ("slip_id.date_from", ">=", date_from),
                ("slip_id.date_to", "<=", date_to),
                ("slip_id.state", "in", ("done", "paid")),
            ],
            order="slip_id, sequence",
        )
        for line in lines:
            result.setdefault(line.register_id.id, self.env["hr.payslip.line"])
            result[line.register_id.id] += line
        return result

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data or not data.get("form"):
            raise UserError(_("No data for this report."))
        form = data["form"]
        register_ids = data.get("ids") or self.env.context.get("active_ids", [])
        registers = self.env["hr.contribution.register"].browse(register_ids)
        date_from = form.get("date_from") or fields.Date.today()
        date_to = form.get("date_to") or fields.Date.to_date(
            datetime.now() + relativedelta(months=+1, day=1, days=-1)
        )
        lines_data = self._get_payslip_lines(set(register_ids), date_from, date_to)
        totals = {}
        for reg in registers:
            lines = lines_data.get(reg.id)
            totals[reg.id] = sum(lines.mapped("total")) if lines else 0.0
        return {
            "doc_ids": register_ids,
            "docs": registers,
            "lines_data": lines_data,
            "lines_total": totals,
        }
