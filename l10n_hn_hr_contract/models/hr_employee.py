# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # El campo wage ya existe relacionado con version_id.wage en hr.employee base
    # pero asegurémonos de que sea editable
    wage = fields.Monetary(
        related="version_id.wage",
        inherited=True,
        readonly=False,
        groups="hr.group_hr_manager",
    )
    extra_time_off = fields.Float(
        string="Días adicionales",
        related="version_id.holidays",
        readonly=True,
        groups="hr.group_hr_manager",
    )
    holidays = fields.Float(
        string="Días adicionales",
        related="version_id.holidays",
        readonly=False,
        groups="hr.group_hr_manager",
    )
    wage_with_holidays = fields.Monetary(
        related="version_id.wage_with_holidays",
        inherited=True,
        readonly=False,
        groups="hr.group_hr_manager",
    )
    wage_on_signature = fields.Monetary(
        related="version_id.wage_on_signature",
        inherited=True,
        readonly=False,
        groups="hr.group_hr_manager",
    )
    final_yearly_costs = fields.Monetary(
        related="version_id.final_yearly_costs",
        inherited=True,
        readonly=False,
        groups="hr.group_hr_manager",
    )
    monthly_yearly_costs = fields.Monetary(
        related="version_id.monthly_yearly_costs",
        inherited=True,
        readonly=False,
        groups="hr.group_hr_manager",
    )
    leave_allocation_id = fields.Many2one(
        related="version_id.leave_allocation_id",
        inherited=True,
        readonly=True,
        groups="hr.group_hr_manager",
    )

    def action_generate_timeoff_allocation(self):
        self.ensure_one()
        return self.version_id.action_generate_timeoff_allocation()

    def action_view_leave_allocation(self):
        self.ensure_one()
        return self.version_id.action_view_leave_allocation()

