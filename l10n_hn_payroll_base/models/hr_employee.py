# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    slip_ids = fields.One2many("hr.payslip", "employee_id", string="Payslips", readonly=True)
    salary_attachment_ids = fields.Many2many(
        "hr.salary.attachment",
        "hr_salary_attachment_hr_employee_rel",
        "employee_id",
        "hr_salary_attachment_id",
        string="Salary adjustments",
        groups="l10n_hn_payroll_base.group_hn_payroll_user",
    )
    payslip_count = fields.Integer(
        compute="_compute_payslip_count",
        string="Payslip Count",
        groups="l10n_hn_payroll_base.group_hn_payroll_user",
    )
    struct_id = fields.Many2one(
        related="version_id.struct_id",
        readonly=False,
        inherited=True,
        groups="hr.group_hr_user",
    )
    schedule_pay = fields.Selection(
        related="version_id.schedule_pay",
        readonly=False,
        inherited=True,
        groups="hr.group_hr_user",
    )

    def _compute_payslip_count(self):
        for employee in self:
            employee.payslip_count = len(employee.slip_ids)

    # Same visibility as Enterprise payroll for the Salary Information tab on hr.employee.
    contract_date_start = fields.Date(
        readonly=False,
        related="version_id.contract_date_start",
        inherited=True,
        groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user",
    )
    contract_date_end = fields.Date(
        readonly=False,
        related="version_id.contract_date_end",
        inherited=True,
        groups="hr.group_hr_manager,l10n_hn_payroll_base.group_hn_payroll_user",
    )

    def action_open_hn_payslips(self):
        """Open payslips for this employee (Enterprise stat button behavior)."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_hn_payroll_base.action_view_hr_payslip_form"
        )
        return {
            **action,
            "domain": [("employee_id", "=", self.id)],
            "context": {**self.env.context, "default_employee_id": self.id},
        }

    def action_print_employee_declaration(self):
        self.ensure_one()
        ver = self.version_id
        if not ver:
            raise UserError(_("No hay versión de contrato vigente para imprimir la constancia."))
        return ver.action_print_employee_declaration()

    def action_print_employee_cancelled_declaration(self):
        self.ensure_one()
        ver = self.version_id
        if not ver:
            raise UserError(_("No hay versión de contrato vigente para imprimir la constancia."))
        return ver.action_print_employee_cancelled_declaration()
