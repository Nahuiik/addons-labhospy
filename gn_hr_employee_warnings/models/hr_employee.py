# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from markupsafe import Markup, escape

from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _gn_hr_warning_low_net_pay_ratio(self):
        """Fracción mínima líquido/bruto en quincena; fuera de rango se recorta."""
        raw = self.env["ir.config_parameter"].sudo().get_param(
            "gn_hr_employee_warnings.low_net_pay_gross_remaining_percent",
            "25",
        )
        try:
            pct = int(str(raw).strip())
        except (TypeError, ValueError):
            pct = 25
        pct = max(1, min(pct, 95))
        return pct / 100.0

    contract_expiring_soon = fields.Boolean(
        string="Contrato por vencer",
        compute="_compute_contract_expiring_soon",
        help="True si el contrato vence dentro de los días configurados en ajustes.",
    )
    days_to_contract_expiration = fields.Integer(
        string="Días para vencimiento",
        compute="_compute_contract_expiring_soon",
        help="Días restantes hasta la fecha de terminación del contrato.",
    )
    contract_expiration_warning_message = fields.Char(
        string="Mensaje alerta contrato",
        compute="_compute_contract_expiring_soon",
    )

    def _get_contract_expiration_warning_days(self):
        ICP = self.env["ir.config_parameter"].sudo()
        val = ICP.get_param("gn_hr_employee_warnings.contract_expiration_warning_days")
        if val is None or val == "":
            val = ICP.get_param("l10n_hn_hr_payroll.contract_expiration_warning_days", "30")
        try:
            return int(val)
        except (TypeError, ValueError):
            return 30

    def _get_loan_ending_installments_threshold(self):
        ICP = self.env["ir.config_parameter"].sudo()
        val = ICP.get_param(
            "gn_hr_employee_warnings.loan_ending_installments_threshold", "3"
        )
        try:
            return max(0, int(val))
        except (TypeError, ValueError):
            return 3

    @api.depends("current_version_id", "current_version_id.contract_date_end")
    def _compute_contract_expiring_soon(self):
        today = fields.Date.context_today(self)
        warning_days = self._get_contract_expiration_warning_days()
        WarningType = self.env["hr.employee.warning.type"]
        if not WarningType._is_warning_active("CONTRACT_EXPIRY"):
            for emp in self:
                emp.contract_expiring_soon = False
                emp.days_to_contract_expiration = 0
                emp.contract_expiration_warning_message = ""
            return
        for emp in self:
            version = emp._gn_hr_sudo_current_version()
            end_date = version.contract_date_end if version else None
            if not end_date or end_date < today:
                emp.contract_expiring_soon = False
                emp.days_to_contract_expiration = 0
                emp.contract_expiration_warning_message = ""
                continue
            delta = (end_date - today).days
            emp.days_to_contract_expiration = delta
            emp.contract_expiring_soon = delta <= warning_days
            if emp.contract_expiring_soon:
                emp.contract_expiration_warning_message = (
                    f"El contrato vence el {end_date.strftime('%d/%m/%Y')} "
                    f'({delta} día{"s" if delta != 1 else ""} restante{"s" if delta != 1 else ""}).'
                )
            else:
                emp.contract_expiration_warning_message = ""

    parent_type_warning = fields.Char(
        string="Alerta Padre/Madre",
        compute="_compute_warn_parent",
        store=False,
    )
    has_parent_type_warning = fields.Boolean(
        string="Tiene alerta Padre/Madre",
        compute="_compute_warn_parent",
        store=False,
    )

    def _compute_warn_parent(self):
        """Sobrescrito en l10n_hn_hr_payroll cuando aplica datos familiares HN."""
        for emp in self:
            emp.parent_type_warning = False
            emp.has_parent_type_warning = False

    loan_ending_soon_warning = fields.Html(
        string="Alerta préstamo por terminar",
        compute="_compute_loan_ending_soon_warning",
        sanitize=False,
    )
    has_loan_ending_soon_warning = fields.Boolean(
        string="Préstamo con pocas cuotas restantes",
        compute="_compute_loan_ending_soon_warning",
    )

    @api.depends(
        "recurring_concept_ids",
        "recurring_concept_ids.active",
        "recurring_concept_ids.is_loan",
        "recurring_concept_ids.is_template",
        "recurring_concept_ids.concept_type",
        "recurring_concept_ids.installments",
        "recurring_concept_ids.paid_installments",
        "recurring_concept_ids.name",
    )
    def _compute_loan_ending_soon_warning(self):
        WarningType = self.env["hr.employee.warning.type"]
        if not WarningType._is_warning_active("LOAN_ENDING_SOON"):
            for emp in self:
                emp.has_loan_ending_soon_warning = False
                emp.loan_ending_soon_warning = False
            return
        threshold = self._get_loan_ending_installments_threshold()
        if threshold <= 0:
            for emp in self:
                emp.has_loan_ending_soon_warning = False
                emp.loan_ending_soon_warning = False
            return
        for emp in self:
            lines = []
            for concept in emp.recurring_concept_ids:
                if (
                    not concept.active
                    or concept.is_template
                    or not concept.is_loan
                    or concept.concept_type != "deduction"
                ):
                    continue
                total = concept.installments or 0
                paid = concept.paid_installments or 0
                remaining = total - paid
                if remaining <= 0 or remaining > threshold:
                    continue
                lines.append(
                    escape(concept.name or "")
                    + ": "
                    + _(
                        "%(n)d cuota(s) pendiente(s) (de %(tot)d).",
                        n=remaining,
                        tot=total,
                    )
                )
            if lines:
                emp.has_loan_ending_soon_warning = True
                emp.loan_ending_soon_warning = "<br/>".join(lines)
            else:
                emp.has_loan_ending_soon_warning = False
                emp.loan_ending_soon_warning = False

    license_expiration_warning = fields.Html(
        string="Alerta de Licencias",
        compute="_compute_license_expiration_warning",
        store=False,
    )
    has_expiring_licenses = fields.Boolean(
        string="Tiene Licencias por Vencer",
        compute="_compute_license_expiration_warning",
        store=False,
    )

    @api.depends("license_ids", "license_ids.expiration_date", "license_ids.is_expired")
    def _compute_license_expiration_warning(self):
        WarningType = self.env["hr.employee.warning.type"]
        if not WarningType._is_warning_active("LICENSE_EXPIRY"):
            for employee in self:
                employee.has_expiring_licenses = False
                employee.license_expiration_warning = False
            return
        today = fields.Date.today()
        for employee in self:
            warnings = []
            for lic in employee.license_ids:
                if lic.expiration_date:
                    if lic.is_expired:
                        warnings.append(
                            _(
                                '%s: <strong class="text-danger">VENCIDA</strong> (%s)'
                            )
                            % (lic.license_type_id.name, lic.time_to_expire)
                        )
                    else:
                        days_to_expire = (lic.expiration_date - today).days
                        if days_to_expire <= 30:
                            warnings.append(
                                _(
                                    '%s: <strong class="text-warning">Por vencer</strong> (%s)'
                                )
                                % (lic.license_type_id.name, lic.time_to_expire)
                            )

            if warnings:
                employee.has_expiring_licenses = True
                employee.license_expiration_warning = "<br/>".join(warnings)
            else:
                employee.has_expiring_licenses = False
                employee.license_expiration_warning = False

    missing_bank_account_warning = fields.Html(
        string="Alerta sin cuenta bancaria",
        compute="_compute_missing_bank_account_warning",
        sanitize=False,
    )
    has_missing_bank_account_warning = fields.Boolean(
        string="Sin cuenta bancaria",
        compute="_compute_missing_bank_account_warning",
    )

    @api.depends("bank_account_ids")
    def _compute_missing_bank_account_warning(self):
        WarningType = self.env["hr.employee.warning.type"]
        if not WarningType._is_warning_active("MISSING_BANK_ACCOUNT"):
            for employee in self:
                employee.has_missing_bank_account_warning = False
                employee.missing_bank_account_warning = False
            return
        for employee in self:
            if employee.bank_account_ids:
                employee.has_missing_bank_account_warning = False
                employee.missing_bank_account_warning = False
            else:
                employee.has_missing_bank_account_warning = True
                employee.missing_bank_account_warning = _(
                    "<strong>Sin cuenta bancaria:</strong> configure una cuenta en la pestaña Personal "
                    "para el pago de salario."
                )

    employee_form_alerts_panel_html = fields.Html(
        string="Panel de alertas en ficha",
        compute="_compute_employee_form_alerts_panel",
        sanitize=False,
    )
    employee_form_alerts_panel_visible = fields.Boolean(
        compute="_compute_employee_form_alerts_panel",
    )

    @api.depends(
        "has_expiring_licenses",
        "license_expiration_warning",
        "has_missing_documents",
        "missing_documents_warning",
        "contract_expiring_soon",
        "contract_expiration_warning_message",
        "has_loan_missing_dates_warning",
        "loan_missing_dates_warning",
        "has_loan_ending_soon_warning",
        "loan_ending_soon_warning",
        "has_parent_type_warning",
        "parent_type_warning",
        "has_trial_period_warning",
        "trial_period_warning",
        "has_low_net_pay_quincena_warning",
        "low_net_pay_quincena_warning_message",
        "has_missing_bank_account_warning",
        "missing_bank_account_warning",
    )
    def _compute_employee_form_alerts_panel(self):
        for emp in self:
            rows = []
            if emp.has_expiring_licenses and emp.license_expiration_warning:
                rows.append(
                    Markup(
                        '<div class="mb-2"><span class="fw-bold text-danger">%s</span><br/>%s</div>'
                    )
                    % (_("Licencias"), Markup(emp.license_expiration_warning))
                )
            if emp.has_missing_documents and emp.missing_documents_warning:
                rows.append(
                    Markup('<div class="mb-2">%s</div>') % Markup(emp.missing_documents_warning)
                )
            if emp.contract_expiring_soon and emp.contract_expiration_warning_message:
                rows.append(
                    Markup('<div class="mb-2"><span class="fw-bold">%s</span> %s</div>')
                    % (_("Contrato por vencer:"), escape(emp.contract_expiration_warning_message))
                )
            if emp.has_missing_bank_account_warning and emp.missing_bank_account_warning:
                rows.append(
                    Markup('<div class="mb-2">%s</div>') % Markup(emp.missing_bank_account_warning)
                )
            if emp.has_loan_missing_dates_warning and emp.loan_missing_dates_warning:
                rows.append(
                    Markup('<div class="mb-2">%s</div>') % Markup(emp.loan_missing_dates_warning)
                )
            if emp.has_loan_ending_soon_warning and emp.loan_ending_soon_warning:
                rows.append(
                    Markup(
                        '<div class="mb-2 text-info"><i class="fa fa-flag-checkered me-1"></i>'
                        "<strong>%s</strong><br/>%s</div>"
                    )
                    % (_("Préstamo por terminar:"), Markup(emp.loan_ending_soon_warning))
                )
            if emp.has_parent_type_warning and emp.parent_type_warning:
                rows.append(
                    Markup('<div class="mb-2"><span class="fw-bold">%s</span> %s</div>')
                    % (_("Datos familiares:"), escape(emp.parent_type_warning))
                )
            if emp.has_trial_period_warning and emp.trial_period_warning:
                rows.append(
                    Markup(
                        '<div class="mb-2 text-info"><i class="fa fa-hourglass-half me-1"></i>%s</div>'
                    )
                    % escape(emp.trial_period_warning)
                )
            if emp.has_low_net_pay_quincena_warning and emp.low_net_pay_quincena_warning_message:
                rows.append(
                    Markup(
                        '<div class="mb-2 text-danger"><i class="fa fa-percent me-1"/><strong>%s</strong> %s</div>'
                    )
                    % (
                        _("Líquido quincenal bajo:"),
                        escape(emp.low_net_pay_quincena_warning_message),
                    )
                )
            if rows:
                emp.employee_form_alerts_panel_html = Markup(
                    '<div class="alert alert-light border mb-3 py-3" role="alert">%s</div>'
                ) % Markup("").join(rows)
                emp.employee_form_alerts_panel_visible = True
            else:
                emp.employee_form_alerts_panel_html = False
                emp.employee_form_alerts_panel_visible = False

    active_warnings_display = fields.Char(
        string="Alertas activas",
        compute="_compute_active_warnings_display",
        search="_search_active_warnings_display",
        store=False,
    )

    def _compute_active_warnings_display(self):
        warning_types = self.env["hr.employee.warning.type"].search(
            [("active", "=", True), ("employee_field", "!=", False)], order="sequence"
        )
        for emp in self:
            names = []
            for wt in warning_types:
                if getattr(emp, wt.employee_field, False):
                    names.append(wt.name)
            emp.active_warnings_display = ", ".join(names) if names else False

    def _search_active_warnings_display(self, operator, value):
        warning_types = self.env["hr.employee.warning.type"].search(
            [("active", "=", True), ("employee_field", "!=", False)]
        )
        if not warning_types:
            if operator in ("!=", "not like", "not ilike"):
                return [("id", "=", False)]
            return [("id", "in", [])]

        warning_fields = [wt.employee_field for wt in warning_types]
        want_with_warnings = (
            (operator == "!=" and not value)
            or (operator == "=" and value)
            or (operator not in ("=", "!="))
        )

        employees = self.env["hr.employee"].with_context(active_test=True).search(
            [("active", "=", True)], order="id"
        )
        BATCH = 200
        matching_ids = []
        for i in range(0, len(employees), BATCH):
            batch = employees[i : i + BATCH]
            for emp in batch:
                if any(getattr(emp, f, False) for f in warning_fields):
                    matching_ids.append(emp.id)
            employees.invalidate_recordset(warning_fields)

        if want_with_warnings:
            return [("id", "in", matching_ids)]
        return [("id", "not in", matching_ids)]
