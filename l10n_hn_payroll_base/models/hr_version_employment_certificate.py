# -*- coding: utf-8 -*-
"""Constancias de empleo (PDF) sobre hr.version (Odoo 19 CE)."""

from datetime import datetime

import pytz
from babel.dates import format_date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None


class HrVersion(models.Model):
    _inherit = "hr.version"

    wage_in_words = fields.Char(compute="_compute_employment_certificate_fields", string="Salario en letras")
    date_start_text = fields.Char(
        string="Fecha inicio (texto)",
        compute="_compute_employment_certificate_fields",
    )
    date_end_text = fields.Char(
        string="Fecha fin (texto)",
        compute="_compute_employment_certificate_fields",
    )
    afp_atlantida_amount = fields.Float(
        string="AFP Atlántida",
        compute="_compute_employment_certificate_fields",
        digits=(12, 2),
    )
    cert_ihss_monthly = fields.Float(
        string="IHSS (constancia)",
        compute="_compute_employment_certificate_fields",
        digits=(12, 2),
    )
    cert_rap = fields.Float(
        string="RAP (constancia)",
        compute="_compute_employment_certificate_fields",
        digits=(12, 2),
    )
    cert_isr = fields.Float(
        string="ISR (constancia)",
        compute="_compute_employment_certificate_fields",
        digits=(12, 2),
    )

    def _ensure_signature_dependencies(self):
        if BeautifulSoup is None:
            raise UserError(_("No se puede validar la firma: instale la librería python \"bs4\" (beautifulsoup4)."))

    def _check_employment_certificate_requirements(self):
        for contract in self:
            contract_name = contract.name or ""
            if not contract.hr_responsible_id:
                raise UserError(
                    _(
                        'No se puede imprimir la constancia de trabajo para la versión "%s": '
                        "no tiene un responsable asignado."
                    )
                    % contract_name
                )

            signature_html = contract.hr_responsible_id.signature or ""
            soup = BeautifulSoup(signature_html, "html.parser")
            text_content = soup.get_text(strip=True)
            if not text_content:
                raise UserError(
                    _(
                        'No se puede imprimir la constancia de trabajo para la versión "%s": '
                        "el responsable no tiene asignada una firma."
                    )
                    % contract_name
                )

            if not contract.employee_id:
                raise UserError(
                    _(
                        'No se puede imprimir la constancia de trabajo para la versión "%s": '
                        "no está asignada a un empleado."
                    )
                    % contract_name
                )
            if not contract.job_id:
                raise UserError(
                    _(
                        'No se puede imprimir la constancia de trabajo para la versión "%s": '
                        "no tiene un cargo asignado."
                    )
                    % contract_name
                )
            if not contract.date_start:
                raise UserError(
                    _(
                        'No se puede imprimir la constancia de trabajo para la versión "%s": '
                        "no tiene fecha de inicio."
                    )
                    % contract_name
                )
            if not contract.wage:
                raise UserError(
                    _(
                        'No se puede imprimir la constancia de trabajo para la versión "%s": '
                        "no tiene salario asignado."
                    )
                    % contract_name
                )

    def action_print_employee_declaration(self):
        self._ensure_signature_dependencies()
        self._check_employment_certificate_requirements()
        return self.env.ref("l10n_hn_payroll_base.action_report_employee_declaration").report_action(self)

    def action_print_employee_cancelled_declaration(self):
        self._ensure_signature_dependencies()
        self._check_employment_certificate_requirements()
        return self.env.ref("l10n_hn_payroll_base.action_report_employee_cancelled_declaration").report_action(
            self
        )

    def _get_report_base_filename(self):
        self.ensure_one()
        return "CONSTANCIA %s" % (self.employee_id.name if self.employee_id else "Empleado")

    def _get_afp_atlantida_amount(self):
        self.ensure_one()
        if "benefit_line_ids" not in self._fields:
            return 0.0
        for line in self.benefit_line_ids:
            if line.name == "AFP ATLANTIDA":
                return line.amount_employee or 0.0
        return 0.0

    def _get_cert_ihss_amount(self):
        self.ensure_one()
        if "ihss_amount_monthly" not in self._fields:
            return 0.0
        if getattr(self, "ihss_manual", False):
            return self.amount_ihss_manual or 0.0
        return self.ihss_amount_monthly or 0.0

    def _get_cert_rap_amount(self):
        self.ensure_one()
        if "rap_fee" not in self._fields:
            return 0.0
        if getattr(self, "rap_manual", False):
            return self.amount_rap_manual or 0.0
        if self.rap_fee:
            return self.rap_fee
        return self.rap_foviif_amount_monthly or 0.0

    def _get_cert_isr_amount(self):
        self.ensure_one()
        if "amount_isr_calculated" not in self._fields:
            return 0.0
        if getattr(self, "isr_manual", False):
            return self.amount_isr_manual or 0.0
        return self.amount_isr_calculated or 0.0

    def get_today_in_words(self):
        tz_honduras = pytz.timezone("America/Tegucigalpa")
        today = datetime.now(tz_honduras)
        return format_date(today, "d 'del mes de' MMMM 'del año' y", locale="es_ES")

    @api.depends(
        "wage",
        "currency_id",
        "date_start",
        "date_end",
        "employee_id",
        "company_id",
    )
    def _compute_employment_certificate_fields(self):
        for version in self:
            if version.currency_id and version.wage:
                version.wage_in_words = version.currency_id.amount_to_text(version.wage).upper()
            else:
                version.wage_in_words = ""

            if version.date_start:
                version.date_start_text = format_date(
                    version.date_start, "d 'de' MMMM 'de' y", locale="es_ES"
                )
            else:
                version.date_start_text = ""

            if version.date_end:
                version.date_end_text = format_date(version.date_end, "d 'de' MMMM 'de' y", locale="es_ES")
            else:
                version.date_end_text = ""

            version.afp_atlantida_amount = version._get_afp_atlantida_amount()
            version.cert_ihss_monthly = version._get_cert_ihss_amount()
            version.cert_rap = version._get_cert_rap_amount()
            version.cert_isr = version._get_cert_isr_amount()
