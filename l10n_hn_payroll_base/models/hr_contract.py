# -*- coding: utf-8 -*-
"""Contract (hr.version) extensions for payroll structures."""

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

    hours_per_week = fields.Float(
        related="resource_calendar_id.hours_per_week",
        string="Hours per week",
        groups="hr.group_hr_user",
        readonly=True,
    )
    disabled = fields.Boolean(
        string="Disabled",
        help="If the employee is declared disabled by law.",
        tracking=True,
    )

    struct_id = fields.Many2one("hr.payroll.structure", string="Salary Structure")
    schedule_pay = fields.Selection(
        selection=lambda self: self.env["hr.payroll.structure.type"]._get_selection_schedule_pay(),
        default="monthly",
        index=True,
        help="Wage payment frequency.",
    )
    structure_wage_type = fields.Selection(
        related="structure_type_id.wage_type",
        string="Wage type",
        readonly=True,
    )
    wage_period_display = fields.Char(
        string="Wage period",
        compute="_compute_wage_period_display",
    )
    employer_annual_cost = fields.Monetary(
        string="Employer cost (annual)",
        compute="_compute_employer_annual_cost",
        currency_field="currency_id",
        help="Indicative annual amount from wage, pay frequency and wage type (summary similar to Enterprise).",
    )
    payslip_input_template_line_ids = fields.One2many(
        "hr.version.payslip.input.template",
        "version_id",
        string="Default payslip inputs",
        copy=True,
        help="Optional defaults for payslip input lines (benefits, deductions). "
        "Linked input types should be allowed on the contract salary structure, or the structure must leave "
        '"Other input lines" unrestricted.',
    )
    payslips_count = fields.Integer(
        string="# Payslips",
        compute="_compute_payslips_count",
        groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user",
    )

    @api.depends("schedule_pay", "structure_type_id.wage_type")
    def _compute_wage_period_display(self):
        unit = {
            "monthly": "month",
            "semi-monthly": "half-month",
            "quarterly": "quarter",
            "semi-annually": "half-year",
            "annually": "year",
            "weekly": "week",
            "bi-weekly": "2 weeks",
            "bi-monthly": "2 months",
            "daily": "day",
        }
        for rec in self:
            if rec.structure_wage_type == "hourly":
                rec.wage_period_display = "/ hour"
                continue
            key = rec.schedule_pay or "monthly"
            rec.wage_period_display = f"/ {unit.get(key, 'period')}"

    def _compute_payslips_count(self):
        """Número de recibos vinculados (campo equivalente a Enterprise hr_payroll)."""
        for rec in self:
            rec.payslips_count = 0
        if not self.ids:
            return
        Payslip = self.env["hr.payslip"].sudo()
        grouped = Payslip._read_group(
            [("contract_id", "in", self.ids)],
            ["contract_id"],
            ["__count"],
        )
        counts = {}
        for contract, count in grouped:
            if contract:
                counts[contract.id] = count
        for rec in self:
            rec.payslips_count = counts.get(rec.id, 0)

    @api.depends(
        "wage",
        "schedule_pay",
        "structure_type_id",
        "structure_type_id.wage_type",
        "structure_type_id.default_schedule_pay",
        "resource_calendar_id.hours_per_week",
    )
    def _compute_employer_annual_cost(self):
        mult_by_schedule = {
            "monthly": 12,
            "semi-monthly": 24,
            "bi-monthly": 6,
            "quarterly": 4,
            "semi-annually": 2,
            "annually": 1,
            "weekly": 52,
            "bi-weekly": 26,
            "daily": 260,
        }
        hr_to_odoo_schedule = {
            "monthly": "monthly",
            "semi-monthly": "semi-monthly",
            "quarterly": "quarterly",
            "semi-annually": "semi-annually",
            "annually": "annually",
            "weekly": "weekly",
            "bi-weekly": "bi-weekly",
            "bi-monthly": "bi-monthly",
            "daily": "daily",
        }
        for rec in self:
            wage = rec.wage or 0.0
            if not wage:
                rec.employer_annual_cost = 0.0
                continue
            wage_kind = rec.structure_type_id.wage_type if rec.structure_type_id else "monthly"
            if wage_kind == "hourly":
                hours = rec.resource_calendar_id.hours_per_week if rec.resource_calendar_id else 40.0
                rec.employer_annual_cost = wage * (hours or 0.0) * 52
                continue
            key = hr_to_odoo_schedule.get(rec.schedule_pay or "", "")
            if not key and rec.structure_type_id and rec.structure_type_id.default_schedule_pay:
                key = rec.structure_type_id.default_schedule_pay
            if not key:
                key = "monthly"
            factor = mult_by_schedule.get(key, 12)
            rec.employer_annual_cost = wage * factor

    # Widen contract/salary fields to payroll officers (mirrors Enterprise hr_payroll on hr.version).
    contract_date_start = fields.Date(
        groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user"
    )
    contract_date_end = fields.Date(
        groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user"
    )
    wage = fields.Monetary(groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user")
    contract_wage = fields.Monetary(
        groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user"
    )
    structure_type_id = fields.Many2one(
        groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user"
    )
    contract_type_id = fields.Many2one(
        groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user"
    )

    def get_all_structures(self):
        """Return structure ids including parents, without duplicates."""
        structures = self.mapped("struct_id")
        if not structures:
            return []
        return list(set(structures._get_parent_structure().ids))

    def get_attribute(self, code, attribute):
        """Legacy helper to read a value from advantage templates by code."""
        template = self.env["hr.version.advantage.template"].search([("code", "=", code)], limit=1)
        if not template:
            return False
        return template[attribute]

    def set_attribute_value(self, code, active):
        """Set dynamic numeric contract fields when the field code exists."""
        tpl = self.env["hr.version.advantage.template"].search([("code", "=", code)], limit=1)
        if not tpl:
            return
        field_name = tpl.code
        for contract in self:
            if field_name not in contract._fields:
                continue
            if active:
                contract[field_name] = tpl.default_value
            else:
                contract[field_name] = 0.0
