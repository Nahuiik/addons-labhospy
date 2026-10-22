# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

import base64
import io
import re
import zipfile
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _gn_calendar_month_selection(records):
    """Mes 1–12 para agrupar cumpleaños / inicio de contrato sin año (read_group).

    Odoo invoca los callables de selection con el recordset del modelo como primer argumento.
    """
    return [
        ("1", _("January")),
        ("2", _("February")),
        ("3", _("March")),
        ("4", _("April")),
        ("5", _("May")),
        ("6", _("June")),
        ("7", _("July")),
        ("8", _("August")),
        ("9", _("September")),
        ("10", _("October")),
        ("11", _("November")),
        ("12", _("December")),
    ]


class HrEmployee(models.Model):
    _inherit = "hr.employee"
    _mailing_enabled = True

    birthday_group_month = fields.Selection(
        selection=_gn_calendar_month_selection,
        string="Mes (cumpleaños)",
        compute="_compute_birthday_and_contract_month_group",
        store=True,
        readonly=True,
    )
    contract_start_group_month = fields.Selection(
        selection=_gn_calendar_month_selection,
        string="Mes (inicio contrato)",
        compute="_compute_birthday_and_contract_month_group",
        store=True,
        readonly=True,
    )

    @api.depends("birthday", "contract_date_start")
    def _compute_birthday_and_contract_month_group(self):
        for emp in self:
            emp.birthday_group_month = str(emp.birthday.month) if emp.birthday else False
            emp.contract_start_group_month = (
                str(emp.contract_date_start.month) if emp.contract_date_start else False
            )

    @api.model
    def _gn_hr_employee_write_strip_empty_version_dates(self, vals):
        """No reenviar date_version vacío al hr.version delegado (_inherits) ni disparar inversos."""
        if not isinstance(vals, dict):
            return vals
        vals = dict(vals)
        for fname in (
            "date_version",
            "current_date_version",
            "l10n_sv_current_date_version",
        ):
            if fname in vals and not vals[fname]:
                vals.pop(fname, None)
        return vals

    def write(self, vals):
        vals = self._gn_hr_employee_write_strip_empty_version_dates(vals)
        return super().write(vals)

    def _gn_hr_sudo_current_version(self):
        """Contrato vigente del empleado sin ACL ni prefetch del jefe (hr.version).

        Solo devuelve versión si la compañía del empleado está entre las permitidas
        al usuario (``env.companies``).
        """
        self.ensure_one()
        # Creación/onchange: id virtual (NewId) no es serializable por psycopg2.
        if not isinstance(self.id, int):
            return self.env["hr.version"]
        self.env.cr.execute(
            """
            SELECT company_id, current_version_id
            FROM hr_employee
            WHERE id = %s
            """,
            (self.id,),
        )
        row = self.env.cr.fetchone()
        if not row or row[0] not in self.env.companies.ids or not row[1]:
            return self.env["hr.version"]
        return self.sudo().env["hr.version"].browse(row[1])

    @api.model
    def _gn_hr_contract_days_to_expiration(self, version, today=None):
        """Días hasta fin de contrato a partir de hr.version (reportes, sin compute del empleado)."""
        if not version or not version.contract_date_end:
            return ""
        today = today or fields.Date.context_today(self)
        end = version.contract_date_end
        if end < today:
            return ""
        return (end - today).days

    def _gn_hr_parent_display_name_map(self):
        """Nombre del jefe inmediato por empleado vía SQL (sin ORM ni hr.version del padre)."""
        if not self:
            return {}
        real_ids = [rid for rid in self.ids if isinstance(rid, int)]
        if not real_ids:
            return {}
        self.env.cr.execute(
            """
            SELECT e.id, COALESCE(p.name, '')
            FROM hr_employee e
            LEFT JOIN hr_employee p ON p.id = e.parent_id
            WHERE e.id = ANY(%s)
            """,
            (real_ids,),
        )
        return dict(self.env.cr.fetchall())

    def _gn_hr_for_payroll_export(self):
        """Recordset listo para exportes Excel sin prefetch de jefes ni sus contratos."""
        return self.with_context(prefetch_fields=False)

    def _gn_hr_parent_display_name(self):
        """Nombre del jefe inmediato para una fila de reporte (cross-compañía seguro)."""
        self.ensure_one()
        return self._gn_hr_parent_display_name_map().get(self.id, "")

    gn_hr_immediate_manager_name = fields.Char(
        string="Nombre Completo del Jefe Inmediato",
        compute="_compute_gn_hr_immediate_manager_name",
    )

    @api.depends("parent_id")
    def _compute_gn_hr_immediate_manager_name(self):
        """Jefe inmediato sin resolver parent_id en ORM (evita prefetch de hr.version del jefe)."""
        names = self._gn_hr_parent_display_name_map()
        for emp in self:
            emp.gn_hr_immediate_manager_name = names.get(emp.id, "")

    @api.model
    @api.readonly
    def web_read_group(
        self,
        domain,
        groupby,
        aggregates=(),
        limit=None,
        offset=0,
        order=None,
        **kwargs,
    ):
        """Mes calendario sin año: el cliente envía campo:month (fecha con año en el truncado)."""
        gb = list(groupby)
        if "birthday:year" not in gb and "birthday:month" in gb:
            gb = ["birthday_group_month" if x == "birthday:month" else x for x in gb]
        if "contract_date_start:year" not in gb and "contract_date_start:month" in gb:
            gb = [
                "contract_start_group_month" if x == "contract_date_start:month" else x
                for x in gb
            ]
        return super().web_read_group(
            domain,
            gb,
            aggregates,
            limit=limit,
            offset=offset,
            order=order,
            **kwargs,
        )

    l10n_gn_contract_overview_readonly = fields.Boolean(
        string="Bloquear resumen de contrato (HN/SV, contrato único, sin nóminas)",
        compute="_compute_l10n_gn_contract_overview_readonly",
        help="Si está activo, la ficha de Nómina no permite editar el resumen de contrato: "
        "cambios solo vía asistente «Editar contrato inicial» (mismas reglas que el botón HN/SV).",
    )

    @api.depends(
        "company_id",
        "company_id.country_id",
        "version_ids",
        "slip_ids",
    )
    def _compute_l10n_gn_contract_overview_readonly(self):
        """Misma condición de negocio que el asistente (sin comprobar permisos de grupo)."""
        for emp in self:
            code = (
                emp.company_id.country_id.code
                if emp.company_id and emp.company_id.country_id
                else False
            )
            if code not in ("HN", "SV") or len(emp.version_ids) != 1 or emp.slip_ids:
                emp.l10n_gn_contract_overview_readonly = False
            else:
                emp.l10n_gn_contract_overview_readonly = True

    gn_hide_create_user_button = fields.Boolean(
        string="Ocultar botón Crear usuario (config)",
        compute="_compute_gn_hide_create_user_button",
    )

    @api.depends("company_id")
    def _compute_gn_hide_create_user_button(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hr.employee.hide_create_user_button", "False")
        )
        hide = str(raw).lower() in ("1", "true", "yes")
        for emp in self:
            emp.gn_hide_create_user_button = hide

    document_ids = fields.One2many(
        "hr.employee.document",
        "employee_id",
        string="Documentos de Entrada",
    )
    missing_documents_warning = fields.Html(
        string="Documentos Faltantes",
        compute="_compute_missing_documents_warning",
        store=False,
    )
    has_missing_documents = fields.Boolean(
        string="Tiene Documentos Faltantes",
        compute="_compute_missing_documents_warning",
        store=False,
    )
    document_missing_required_count = fields.Integer(
        string="Cantidad documentos obligatorios faltantes",
        compute="_compute_document_missing_required_count",
    )
    recurring_concept_ids = fields.One2many(
        "hr.employee.recurring.concept",
        "employee_id",
        string="Conceptos recurrentes",
    )
    recurring_concept_active_count = fields.Integer(
        string="Conceptos activos",
        compute="_compute_recurring_concept_counts",
    )
    recurring_concept_loan_active_count = fields.Integer(
        string="Préstamos activos",
        compute="_compute_recurring_concept_counts",
    )
    has_low_net_pay_quincena_warning = fields.Boolean(
        string="Alerta: líquido quincenal muy bajo",
        compute="_compute_low_net_pay_quincena_warning",
        help="Estimación: deducciones legales + recurrentes absorben casi todo el bruto de la quincena.",
    )
    low_net_pay_quincena_warning_message = fields.Char(
        string="Mensaje líquido quincenal bajo",
        compute="_compute_low_net_pay_quincena_warning",
    )
    has_loan_missing_dates_warning = fields.Boolean(
        string="Préstamo sin fechas",
        compute="_compute_loan_missing_dates_warning",
        store=False,
    )
    loan_missing_dates_warning = fields.Html(
        string="Alerta préstamo sin fechas",
        compute="_compute_loan_missing_dates_warning",
        store=False,
    )

    def _warning_type_active(self, xml_id_code):
        """Si existe hr.employee.warning.type (p. ej. módulo HN), respetar catálogo."""
        if "hr.employee.warning.type" not in self.env:
            return True
        return self.env["hr.employee.warning.type"]._is_warning_active(xml_id_code)

    @api.depends("document_ids", "document_ids.is_missing", "document_ids.is_required")
    def _compute_document_missing_required_count(self):
        for employee in self:
            employee.document_missing_required_count = len(
                employee.document_ids.filtered(
                    lambda d: d.is_missing and d.is_required
                )
            )

    @api.depends("document_ids", "document_ids.is_missing", "document_ids.is_required")
    def _compute_missing_documents_warning(self):
        if not self._warning_type_active("MISSING_DOCS"):
            for employee in self:
                employee.has_missing_documents = False
                employee.missing_documents_warning = False
            return
        for employee in self:
            missing_docs = employee.document_ids.filtered(
                lambda d: d.is_missing and d.is_required
            )
            if missing_docs:
                doc_names = missing_docs.mapped("document_type_id.name")
                employee.has_missing_documents = True
                employee.missing_documents_warning = _(
                    "<strong>Documentos obligatorios faltantes:</strong> %s"
                ) % ", ".join(doc_names)
            else:
                employee.has_missing_documents = False
                employee.missing_documents_warning = False

    @api.depends(
        "recurring_concept_ids",
        "recurring_concept_ids.concept_type",
        "recurring_concept_ids.is_loan",
        "recurring_concept_ids.date_start",
        "recurring_concept_ids.date_end",
    )
    def _compute_loan_missing_dates_warning(self):
        if not self._warning_type_active("LOAN_NO_DATES"):
            for employee in self:
                employee.has_loan_missing_dates_warning = False
                employee.loan_missing_dates_warning = False
            return
        for employee in self:
            loans_missing = employee.recurring_concept_ids.filtered(
                lambda c: c.concept_type == "deduction"
                and c.is_loan
                and c.active
                and (not c.date_start or not c.date_end)
            )
            if loans_missing:
                names = ", ".join(loans_missing.mapped("name"))
                employee.has_loan_missing_dates_warning = True
                employee.loan_missing_dates_warning = _(
                    "<strong>Préstamos con fechas incompletas:</strong> %s. "
                    "Configure fecha de inicio y fecha de fin para calcular correctamente las cuotas."
                ) % names
            else:
                employee.has_loan_missing_dates_warning = False
                employee.loan_missing_dates_warning = False

    @api.depends(
        "recurring_concept_ids",
        "recurring_concept_ids.active",
        "recurring_concept_ids.is_loan",
    )
    def _compute_recurring_concept_counts(self):
        for employee in self:
            active = employee.recurring_concept_ids.filtered("active")
            employee.recurring_concept_active_count = len(active)
            employee.recurring_concept_loan_active_count = len(
                active.filtered("is_loan")
            )

    def action_open_recurring_concepts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Conceptos recurrentes"),
            "res_model": "hr.employee.recurring.concept",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {
                "default_employee_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_open_recurring_loans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Préstamos"),
            "res_model": "hr.employee.recurring.concept",
            "view_mode": "kanban,list,form",
            "domain": [
                ("employee_id", "=", self.id),
                ("is_loan", "=", True),
            ],
            "context": {
                "default_employee_id": self.id,
                "default_company_id": self.company_id.id,
                "default_is_loan": True,
                "default_concept_type": "deduction",
            },
        }

    def action_open_missing_entry_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documentos de entrada"),
            "res_model": "hr.employee.document",
            "view_mode": "list,form",
            "domain": [
                ("employee_id", "=", self.id),
                ("is_missing", "=", True),
                ("is_required", "=", True),
            ],
            "context": {"default_employee_id": self.id},
        }

    def action_generate_required_documents(self):
        self.ensure_one()
        company = self.company_id
        domain = [
            ("is_required", "=", True),
            ("active", "=", True),
        ]
        if company:
            domain.append(("company_id", "=", company.id))
        required_types = self.env["hr.document.type"].search(domain)
        existing_types = self.document_ids.mapped("document_type_id")
        vals_list = [
            {"employee_id": self.id, "document_type_id": dt.id}
            for dt in required_types
            if dt not in existing_types
        ]
        if vals_list:
            self.env["hr.employee.document"].create(vals_list)
        return True

    def _l10n_gn_gross_quincena_estimate(self):
        """Bruto por quincena (estimado) según periodicidad del contrato vigente."""
        self.ensure_one()
        ver = self.current_version_id.sudo() if self.current_version_id else False
        if not ver:
            return 0.0
        wage = ver._get_contract_wage() if hasattr(ver, "_get_contract_wage") else float(ver.wage or 0.0)
        wage = float(wage or 0.0)
        per = (getattr(ver, "periodicity", None) or "").lower()
        sched = (ver.schedule_pay or "").lower() if getattr(ver, "schedule_pay", None) else ""
        if not per and sched in ("bi-weekly", "biweekly"):
            per = "biweekly"
        if per in ("biweekly", "bi-weekly") or sched in ("bi-weekly", "biweekly"):
            return round(wage / 2.0, 2)
        if per == "weekly" or sched == "weekly":
            return round(wage / 4.33 * 2.0, 2)
        return round(wage / 2.0, 2)

    def _gn_payslip_like_calculate_concept_amount(self, concept, date_from, date_to):
        """Replica la base de hr.payslip._calculate_concept_amount (sin líneas de recibo previas)."""
        self.ensure_one()
        if concept.amount_type == "fixed":
            base = concept.amount or 0.0
        elif concept.amount_type == "percentage":
            ver = self.current_version_id.sudo() if self.current_version_id else False
            wage = 0.0
            if ver:
                wage = (
                    ver._get_contract_wage()
                    if hasattr(ver, "_get_contract_wage")
                    else float(ver.wage or 0.0)
                )
            wage = float(wage or 0.0)
            periodicity = (getattr(ver, "periodicity", None) or "monthly").lower()
            if periodicity in ("biweekly", "bi-weekly"):
                period_wage = wage / 2.0
            elif periodicity == "weekly":
                period_wage = wage / 4.33
            else:
                period_wage = wage
            base = (period_wage * (concept.amount or 0.0)) / 100.0
        else:
            base = 0.0
        base = concept._gn_effective_recurring_deduction_base(base)
        return concept._gn_apply_loan_biweek_split_to_amount(base, self, date_from)

    def gn_estimate_recurring_deductions_for_payslip_period(self, date_from, date_to):
        """Total deducciones recurrentes aplicables a [date_from, date_to] (misma lógica que nómina)."""
        self.ensure_one()
        total = 0.0
        concepts = self.recurring_concept_ids.filtered(
            lambda c: c.active
            and not c.is_template
            and c.concept_type == "deduction"
            and c.company_id == self.company_id
        )
        for concept in concepts:
            if concept.date_start and concept.date_start > date_to:
                continue
            if concept.date_end and concept.date_end < date_from:
                continue
            if concept.is_loan and concept.installments and concept._gn_loan_is_complete():
                continue
            if concept.apply_biweek and concept.apply_biweek != "both":
                version_sudo = self.current_version_id.sudo() if self.current_version_id else False
                periodicity = (version_sudo.periodicity or "monthly") if version_sudo else "monthly"
                if periodicity in ("biweekly", "bi-weekly"):
                    df_day = date_from.day
                    is_first = df_day <= 15
                    is_second = df_day >= 16
                    if concept.apply_biweek == "first" and not is_first:
                        continue
                    if concept.apply_biweek == "second" and not is_second:
                        continue
            amount = self._gn_payslip_like_calculate_concept_amount(concept, date_from, date_to)
            if amount:
                total += amount
        return round(total, 2)

    @api.depends(
        "recurring_concept_ids",
        "recurring_concept_ids.active",
        "recurring_concept_ids.is_template",
        "recurring_concept_ids.concept_type",
        "recurring_concept_ids.amount",
        "recurring_concept_ids.amount_type",
        "recurring_concept_ids.date_start",
        "recurring_concept_ids.date_end",
        "recurring_concept_ids.apply_biweek",
        "recurring_concept_ids.is_loan",
        "recurring_concept_ids.installments",
        "recurring_concept_ids.paid_installments",
        "recurring_concept_ids.loan_split_quota_across_biweeks",
        "recurring_concept_ids.loan_first_biweek_amount",
        "current_version_id",
        "current_version_id.wage",
        "current_version_id.schedule_pay",
        "company_id",
    )
    def _compute_low_net_pay_quincena_warning(self):
        """Base: sin país HN/SV no aplica. Localizaciones extienden."""
        for emp in self:
            emp.has_low_net_pay_quincena_warning = False
            emp.low_net_pay_quincena_warning_message = False

    def action_download_all_documents(self):
        self.ensure_one()
        docs = self.document_ids.filtered(lambda d: d.document)
        if not docs:
            raise UserError(_("El empleado no tiene documentos cargados para descargar."))

        def _safe_filename(name):
            return re.sub(r"[^\w\s\-\.]", "_", (name or "").strip()) or "documento"

        emp_name = (self.name or "empleado").strip()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc in docs:
                tipo_name = (
                    doc.document_type_id.name if doc.document_type_id else "documento"
                ).strip()
                ext = doc.file_extension or ""
                if doc.document_filename and "." in doc.document_filename:
                    ext = doc.document_filename.rsplit(".", 1)[-1].lower()
                ext = ext or "bin"
                base_name = f"{emp_name} - {tipo_name}"
                filename = _safe_filename(base_name) + f".{ext}"
                content = base64.b64decode(doc.document)
                zf.writestr(filename, content)

        buffer.seek(0)
        emp_name_safe = _safe_filename(self.name or "empleado")
        emp_id = self.identification_id or str(self.id)
        zip_filename = (
            f"Documentos_{emp_name_safe}_{emp_id}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": zip_filename,
                "type": "binary",
                "datas": base64.b64encode(buffer.read()),
                "res_model": "hr.employee",
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true&filename={zip_filename}",
            "target": "self",
        }
