# -*- coding: utf-8 -*-
"""
Ajustes recurrentes u obligaciones descontadas vía nómina (CE).

Registra montos por periodo, totales opcionales y vínculo opcional a recibos.
Diseñado para convivir con tipos de entrada (`hr.payslip.input.type`) marcados para adjuntos.
"""

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError


class HrSalaryAttachment(models.Model):
    _name = "hr.salary.attachment"
    _description = "Salary adjustment"
    _inherit = ["mail.thread"]
    _rec_name = "description"

    employee_ids = fields.Many2many(
        "hr.employee",
        "hr_salary_attachment_hr_employee_rel",
        "hr_salary_attachment_id",
        "employee_id",
        string="Employees",
        required=True,
        context={"active_test": False},
    )
    employee_count = fields.Integer(compute="_compute_employee_count")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    description = fields.Char(string="Note", tracking=True)
    other_input_type_id = fields.Many2one(
        "hr.payslip.input.type",
        string="Input type",
        required=True,
        tracking=True,
        domain="[('available_in_attachments', '=', True)]",
    )
    duration_type = fields.Selection(
        [
            ("one", "One time"),
            ("limited", "Limited"),
            ("unlimited", "Unlimited"),
        ],
        string="Schedule",
        default="one",
        required=True,
        tracking=True,
    )
    monthly_amount = fields.Monetary(
        string="Per-payslip amount",
        required=True,
        tracking=True,
        help="Amount to apply on each payslip while the adjustment is active.",
    )
    is_refund = fields.Boolean(
        string="Deduct (negative sign)",
        help="When set, localization rules may interpret the amount as a deduction.",
    )
    total_amount = fields.Monetary(
        string="Planned total",
        tracking=True,
        help="For limited schedules: cap on what will be applied before closing.",
    )
    paid_amount = fields.Monetary(string="Applied so far", default=0.0, copy=False)
    remaining_amount = fields.Monetary(
        string="Remaining balance",
        compute="_compute_remaining_amount",
        store=True,
    )
    date_start = fields.Date(string="Start date", required=True, default=fields.Date.today, tracking=True)
    date_end = fields.Date(string="End date", tracking=True)
    state = fields.Selection(
        [("open", "Running"), ("close", "Closed")],
        default="open",
        required=True,
        tracking=True,
        copy=False,
    )
    payslip_ids = fields.Many2many(
        "hr.payslip",
        "hr_payslip_hr_salary_attachment_rel",
        "hr_salary_attachment_id",
        "payslip_id",
        string="Linked payslips",
        copy=False,
    )
    payslip_count = fields.Integer(compute="_compute_payslip_count", string="Payslips")
    has_done_payslip = fields.Boolean(compute="_compute_has_done_payslip")
    attachment = fields.Binary(string="Supporting file", copy=False)
    attachment_name = fields.Char()

    is_quantity = fields.Boolean(related="other_input_type_id.is_quantity")

    @api.depends("employee_ids")
    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec.employee_ids)

    @api.depends("total_amount", "paid_amount", "monthly_amount", "duration_type")
    def _compute_remaining_amount(self):
        for rec in self:
            if rec.duration_type == "unlimited":
                rec.remaining_amount = rec.monthly_amount
            elif rec.total_amount:
                rec.remaining_amount = max(0.0, rec.total_amount - rec.paid_amount)
            else:
                rec.remaining_amount = max(0.0, rec.monthly_amount - rec.paid_amount)

    @api.depends("payslip_ids")
    def _compute_payslip_count(self):
        for rec in self:
            rec.payslip_count = len(rec.payslip_ids)

    @api.depends("payslip_ids.state")
    def _compute_has_done_payslip(self):
        done_states = {"done", "paid"}
        for rec in self:
            rec.has_done_payslip = any(s.state in done_states for s in rec.payslip_ids)

    @api.constrains("monthly_amount", "total_amount", "date_start", "date_end")
    def _check_amounts_and_dates(self):
        for rec in self:
            if rec.monthly_amount <= 0:
                raise UserError(_("Each payslip amount must be greater than zero."))
            if rec.total_amount and rec.total_amount < rec.monthly_amount:
                raise UserError(_("Planned total cannot be less than the per-payslip amount."))
            if rec.date_end and rec.date_start and rec.date_end < rec.date_start:
                raise UserError(_("The end date cannot precede the start date."))

    def action_close(self):
        self.write({"state": "close", "date_end": fields.Date.today()})

    def action_open(self):
        self.write({"state": "open", "date_end": False})

    def action_split(self):
        """Un registro multi-empleado pasa a varios registros de un solo empleado."""
        self.ensure_one()
        if self.employee_count <= 1:
            raise UserError(_("At least two employees are required to split this record."))

        def _vals_for_employee(emp):
            return {
                "employee_ids": [Command.set([emp.id])],
                "company_id": self.company_id.id,
                "description": self.description,
                "other_input_type_id": self.other_input_type_id.id,
                "duration_type": self.duration_type,
                "monthly_amount": self.monthly_amount,
                "total_amount": self.total_amount,
                "paid_amount": 0.0,
                "date_start": self.date_start,
                "state": "open",
                "attachment": self.attachment,
                "attachment_name": self.attachment_name,
                "is_refund": self.is_refund,
            }

        batch = [_vals_for_employee(emp) for emp in self.employee_ids]
        created = self.env["hr.salary.attachment"].create(batch)
        self.unlink()
        return {
            "type": "ir.actions.act_window",
            "name": _("Adjustment records"),
            "res_model": "hr.salary.attachment",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
        }

    def action_open_payslips(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Payslips"),
            "res_model": "hr.payslip",
            "view_mode": "list,form",
            "domain": [("id", "in", self.payslip_ids.ids)],
        }

    def action_open_employee_salary_attachment(self):
        """Ventana modal desde la ficha empleado (contexto `new` sin res_id)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Adjustment"),
            "view_mode": "form",
            "res_model": "hr.salary.attachment",
            "res_id": False if self.env.context.get("new") else self.id,
            "target": "new",
            "context": dict(self.env.context),
        }

    def record_payment(self, amount):
        """Acumula importe aplicado desde hooks de nómina (un empleado por registro)."""
        self.ensure_one()
        if self.employee_count > 1:
            raise UserError(_("Apply payments only when a single employee is linked."))
        if amount <= 0:
            return
        due = self.remaining_amount
        applied = min(amount, due)
        self.paid_amount += applied
        cap = self.total_amount
        if (
            self.duration_type != "unlimited"
            and cap
            and self.paid_amount + 1e-9 >= cap
        ):
            self.action_close()
