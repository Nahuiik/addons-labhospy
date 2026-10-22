# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    in_trial_period = fields.Boolean(
        string="En período de prueba",
        compute="_compute_trial_period",
    )
    trial_period_warning = fields.Char(
        string="Alerta período de prueba",
        compute="_compute_trial_period",
    )
    has_trial_period_warning = fields.Boolean(
        string="Tiene alerta de prueba",
        compute="_compute_trial_period",
    )
    trial_period_notified = fields.Boolean(
        string="Notificado período de prueba",
        default=False,
        help="Indica si ya se envió la notificación de fin de período de prueba.",
    )

    @api.depends("version_ids", "version_ids.contract_date_start", "company_id")
    def _compute_trial_period(self):
        today = fields.Date.context_today(self)
        if "hr.employee.warning.type" in self.env:
            WarningType = self.env["hr.employee.warning.type"]
            if not WarningType._is_warning_active("TRIAL_PERIOD"):
                for emp in self:
                    emp.in_trial_period = False
                    emp.trial_period_warning = False
                    emp.has_trial_period_warning = False
                return
        for emp in self:
            company = emp.company_id
            trial_days = company._get_localization_trial_period_days() if company else 45
            start = emp.sudo()._get_first_contract_date(no_gap=False)
            if not start:
                emp.in_trial_period = False
                emp.trial_period_warning = False
                emp.has_trial_period_warning = False
                continue
            elapsed = (today - start).days
            if 0 <= elapsed < trial_days:
                emp.in_trial_period = True
                remaining = trial_days - elapsed
                end_date = start + relativedelta(days=trial_days)
                emp.trial_period_warning = (
                    "Empleado en período de prueba: %d de %d días "
                    "(%d día%s restante%s, finaliza el %s)."
                    % (
                        elapsed,
                        trial_days,
                        remaining,
                        "s" if remaining != 1 else "",
                        "s" if remaining != 1 else "",
                        end_date.strftime("%d/%m/%Y"),
                    )
                )
                emp.has_trial_period_warning = True
            elif elapsed == trial_days:
                emp.in_trial_period = False
                emp.trial_period_warning = (
                    "El período de prueba de %d días ha finalizado hoy." % trial_days
                )
                emp.has_trial_period_warning = True
            else:
                emp.in_trial_period = False
                emp.trial_period_warning = False
                emp.has_trial_period_warning = False

    historical_salary_increase_ids = fields.One2many(
        "hr.historical.salary.increase",
        "employee_id",
        string="Historial de aumentos salariales",
        help="Registros creados al validar un aumento en Nómina → Aumentos salariales.",
    )

    salary_advance_ids = fields.One2many(
        "salary.advance",
        "employee_id",
        string="Anticipos salariales",
    )
    salary_advance_count = fields.Integer(
        string="Número de anticipos",
        compute="_compute_salary_advance_count",
    )

    @api.depends("salary_advance_ids")
    def _compute_salary_advance_count(self):
        for emp in self:
            emp.salary_advance_count = len(emp.salary_advance_ids)

    def action_open_salary_advances(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "gn_hr_payroll_salary_management.action_salary_advance"
        )
        action = dict(action)
        ctx = dict(action.get("context") or {})
        ctx["default_employee_id"] = self.id
        action.update({
            "domain": [("employee_id", "=", self.id)],
            "context": ctx,
        })
        return action
