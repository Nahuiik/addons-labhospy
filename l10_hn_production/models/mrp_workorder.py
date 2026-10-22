from odoo import models


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def _hn_get_employee_hourly_cost(self):
        self.ensure_one()
        if "employee_costs_hour" in self._fields and self.employee_costs_hour:
            return self.employee_costs_hour
        workcenter = self.workcenter_id
        if "hn_employee_costs_hour" in workcenter._fields:
            return workcenter.hn_employee_costs_hour or 0.0
        return 0.0

    def _hn_get_employee_operation_cost(self, duration_minutes):
        self.ensure_one()
        return (duration_minutes / 60.0) * self._hn_get_employee_hourly_cost()

    def _compute_expected_operation_cost(self, without_employee_cost=False):
        cost = super()._compute_expected_operation_cost(
            without_employee_cost=without_employee_cost
        )
        if without_employee_cost:
            return cost
        return cost + self._hn_get_employee_operation_cost(self.duration_expected)

    def _get_current_theorical_operation_cost(self, without_employee_cost=False):
        cost = super()._get_current_theorical_operation_cost(
            without_employee_cost=without_employee_cost
        )
        if without_employee_cost:
            return cost
        return cost + self._hn_get_employee_operation_cost(self.get_duration())

    def _compute_current_operation_cost(self):
        return super()._compute_current_operation_cost() + self._hn_get_employee_operation_cost(
            self.get_duration()
        )
