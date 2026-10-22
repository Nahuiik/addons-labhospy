# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class HrPayslipEmployees(models.TransientModel):
    _name = "hr.payslip.employees"
    _description = "Generate payslips from a batch"

    employee_ids = fields.Many2many(
        "hr.employee",
        "l10n_hn_payroll_base_hr_payslip_employee_rel",
        "wizard_id",
        "employee_id",
        string="Employees",
    )

    def compute_sheet(self):
        self.ensure_one()
        batch = self.env["hr.payslip.run"].browse(self.env.context.get("active_id"))
        if not batch:
            raise UserError(_("Missing payslip batch."))
        if not self.employee_ids:
            raise UserError(_("Select at least one employee."))
        slips = self.env["hr.payslip"]
        for employee in self.employee_ids:
            data = self.env["hr.payslip"].onchange_employee_id(
                batch.date_start,
                batch.date_end,
                employee.id,
                contract_id=False,
            )
            vals = dict(data["value"])
            vals.pop("line_ids", None)
            wd_raw = vals.pop("worked_days_line_ids", []) or []
            inp_raw = vals.pop("input_line_ids", []) or []
            vals["worked_days_line_ids"] = []
            for item in wd_raw:
                if isinstance(item, dict):
                    vals["worked_days_line_ids"].append((0, 0, item))
                elif isinstance(item, (list, tuple)) and item and item[0] == 0:
                    vals["worked_days_line_ids"].append(item)
            vals["input_line_ids"] = []
            for item in inp_raw:
                if isinstance(item, dict):
                    vals["input_line_ids"].append((0, 0, item))
                elif isinstance(item, (list, tuple)) and item and item[0] == 0:
                    vals["input_line_ids"].append(item)
            vals.update(
                {
                    "employee_id": employee.id,
                    "payslip_run_id": batch.id,
                    "date_from": batch.date_start,
                    "date_to": batch.date_end,
                    "credit_note": batch.credit_note,
                    "company_id": employee.company_id.id,
                }
            )
            slips += self.env["hr.payslip"].with_context(journal_id=batch.journal_id.id).create(vals)
        slips.compute_sheet()
        return {"type": "ir.actions.act_window_close"}
