# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

GN_GROUP = "gn_hr_payroll_employee_extras.group_gn_edit_initial_contract"


class L10nHnEditInitialContractWizard(models.TransientModel):
    _name = "l10n.hn.edit.initial.contract.wizard"
    _description = "Asistente: editar contrato inicial (una versión, sin nóminas)"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="employee_id.company_id",
        readonly=True,
    )
    version_id = fields.Many2one("hr.version", string="Contrato (versión actual)", required=True, readonly=True)

    date_version = fields.Date(string="Fecha de versión (firma / vigencia)")
    contract_date_start = fields.Date()
    contract_date_end = fields.Date()
    trial_date_end = fields.Date()
    # Sin check_company: el comodelo no expone company_id (usa country_id en Odoo 19).
    structure_type_id = fields.Many2one("hr.payroll.structure.type", check_company=False)
    resource_calendar_id = fields.Many2one("resource.calendar", check_company=True)
    schedule_pay = fields.Selection(
        selection=lambda s: s.env["hr.payroll.structure.type"]._get_selection_schedule_pay()
    )
    department_id = fields.Many2one("hr.department", check_company=True)
    job_id = fields.Many2one("hr.job", check_company=True)
    wage = fields.Monetary("Salario (base nómina)")
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    contract_type_id = fields.Many2one("hr.contract.type", check_company=False)
    periodicity = fields.Selection(
        [
            ("weekly", "Weekly"),
            ("biweekly", "Biweekly"),
            ("monthly", "Monthly"),
        ],
        string="Periodicidad (HN)",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        eid = self.env.context.get("default_employee_id") or res.get("employee_id")
        if eid:
            emp = self.env["hr.employee"].browse(eid)
            v = emp.current_version_id
            if v:
                if v.company_id and v.company_id.currency_id and "currency_id" in fields_list:
                    res["currency_id"] = v.company_id.currency_id.id
                res["version_id"] = v.id
                res["date_version"] = v.date_version
                res["contract_date_start"] = v.contract_date_start
                res["contract_date_end"] = v.contract_date_end
                res["trial_date_end"] = v.trial_date_end
                res["structure_type_id"] = v.structure_type_id.id
                res["resource_calendar_id"] = v.resource_calendar_id.id
                if hasattr(v, "schedule_pay"):
                    res["schedule_pay"] = v.schedule_pay
                res["department_id"] = v.department_id.id
                res["job_id"] = v.job_id.id
                res["wage"] = v.wage
                res["contract_type_id"] = v.contract_type_id.id if v.contract_type_id else False
                if hasattr(v, "periodicity"):
                    res["periodicity"] = v.periodicity
        return res

    @api.constrains("employee_id", "version_id")
    def _check_version_employee(self):
        for w in self:
            if w.version_id and w.employee_id and w.version_id.employee_id != w.employee_id:
                raise UserError(
                    _("La versión de contrato no corresponde al empleado.")
                )

    def _ensure_can_apply(self):
        self.ensure_one()
        if not self.env.user.has_group(GN_GROUP):
            raise AccessError(
                _("Necesita el permiso «Nómina: editar contrato inicial (asistente)».")
            )
        code = (self.employee_id.company_id.country_id.code or "")
        if code not in ("HN", "SV"):
            raise UserError(
                _("Este asistente solo aplica a compañías de Honduras o El Salvador.")
            )
        if not self.employee_id._l10n_edit_initial_contract_eligible(code):
            raise UserError(
                _("Solo se puede editar con este asistente un único contrato mientras el empleado "
                  "no tenga recibos de nómina, y con la nómina local adecuada.")
            )

    def action_apply(self):
        self._ensure_can_apply()
        self.ensure_one()
        vals = {
            "date_version": self.date_version,
            "contract_date_start": self.contract_date_start,
            "contract_date_end": self.contract_date_end,
            "trial_date_end": self.trial_date_end,
            "structure_type_id": self.structure_type_id.id,
            "resource_calendar_id": self.resource_calendar_id.id,
            "department_id": self.department_id.id,
            "job_id": self.job_id.id,
            "wage": self.wage,
            "contract_type_id": self.contract_type_id.id,
        }
        if hasattr(self.version_id, "schedule_pay"):
            vals["schedule_pay"] = self.schedule_pay
        if hasattr(self.version_id, "periodicity"):
            vals["periodicity"] = self.periodicity
        self.env["hr.version"].browse(self.version_id.id).sudo().write(vals)
        return {"type": "ir.actions.act_window_close"}
