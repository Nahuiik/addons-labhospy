from odoo import models


class ReportMrpReportMoOverview(models.AbstractModel):
    _inherit = "report.mrp.report_mo_overview"

    def _get_finished_operation_data(self, production, level=0, current_index=False):
        res = super()._get_finished_operation_data(production, level, current_index)
        currency = res["summary"]["currency"]
        done_operation_uom = res["summary"]["uom_name"]
        operations = res["details"]
        employee_index = 0
        for workorder in production.workorder_ids:
            hourly_cost = workorder._hn_get_employee_hourly_cost()
            if not hourly_cost:
                continue
            estimate_cost = workorder._should_estimate_cost()
            duration = (
                workorder.duration_expected
                if estimate_cost
                else workorder.get_duration()
            )
            employee_cost = currency.round((duration / 60.0) * hourly_cost)
            res["summary"]["mo_cost"] += employee_cost
            res["summary"]["real_cost"] += employee_cost
            operations.append(
                {
                    "level": level,
                    "index": f"{current_index}WH{employee_index}",
                    "name": self.env._(
                        "Mano de obra: %(operation)s",
                        operation=workorder.display_name,
                    ),
                    "quantity": duration / 60.0,
                    "uom_name": done_operation_uom,
                    "uom_precision": 4,
                    "unit_cost": hourly_cost,
                    "mo_cost": employee_cost,
                    "mo_cost_decorator": False,
                    "bom_cost": False,
                    "real_cost": employee_cost,
                    "real_cost_decorator": False,
                    "currency_id": currency.id,
                    "currency": currency,
                }
            )
            employee_index += 1
        if employee_index:
            res["summary"]["real_cost_decorator"] = self._get_comparison_decorator(
                res["summary"]["mo_cost"],
                res["summary"]["real_cost"],
                currency.rounding,
            )
        return res
