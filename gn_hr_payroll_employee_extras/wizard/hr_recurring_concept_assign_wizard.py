# Part of Odoo Module — Payroll extras. See LICENSE and COPYRIGHT.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class HrRecurringConceptAssignWizard(models.TransientModel):
    _name = "hr.employee.recurring.concept.assign.wizard"
    _description = "Asignar o desasignar masivamente concepto recurrente a empleados"

    wizard_type = fields.Selection(
        [
            ("assign", "Asignación masiva"),
            ("unassign", "Desasignación masiva"),
        ],
        string="Tipo",
        required=True,
        default="assign",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda s: s.env.company,
    )
    assignment_scope = fields.Selection(
        [
            ("company", "Toda la compañía"),
            ("departments", "Por departamentos"),
            ("employees", "Empleados seleccionados"),
        ],
        string="Ámbito",
        required=True,
        default="company",
    )
    department_ids = fields.Many2many(
        "hr.department",
        string="Departamentos",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Solo empleados de estos departamentos (de la compañía).",
    )
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Empleados",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Solo estos empleados deben estar en la compañía indicada.",
    )

    concept_id = fields.Many2one(
        "hr.employee.recurring.concept",
        string="Plantilla (concepto compartido)",
        domain="[('id', 'in', available_concept_ids)]",
        help="Las líneas heredan este concepto; no se duplica la definición del catálogo.",
    )
    concept_id_locked = fields.Boolean(default=False)

    source_mode = fields.Selection(
        [
            ("shared", "Catálogo"),
            ("inline", "Definir aquí"),
        ],
        string="Origen del concepto",
        required=True,
        default="shared",
    )

    assign_amount = fields.Float(
        string="Monto",
        help="Monto o porcentaje (según el tipo de la plantilla o definición en línea).",
    )
    assign_apply_biweek = fields.Selection(
        [
            ("first", "Sólo 1.ª quincena"),
            ("second", "Sólo 2.ª quincena"),
            ("both", "Ambas quincenas"),
        ],
        string="Aplicar en quincena",
        required=True,
        default="both",
    )
    loan_split_quota_across_biweeks = fields.Boolean(
        string="Dividir monto entre quincenas",
        default=False,
        help="Con «Ambas quincenas» y nómina quincenal: monto explícito en 1.ª quincena; 2.ª = resto. En 0 = mitad y mitad.",
    )
    loan_first_biweek_amount = fields.Float(
        string="Monto 1.ª quincena",
        digits=(12, 2),
        default=0.0,
    )
    first_quota_differentiated = fields.Boolean(
        string="Primera cuota diferenciada",
        default=False,
        help="Solo préstamos: primera cuota pendiente usa el monto primera cuota; el split quincenal aplica sobre ese valor.",
    )
    first_quota_amount = fields.Float(
        string="Monto primera cuota",
        digits=(12, 2),
        default=0.0,
    )
    date_start = fields.Date(string="Fecha inicio", required=True, default=fields.Date.context_today)
    date_end = fields.Date(string="Fecha fin", help="Vacío: sin fecha fin (concepto sin fin).")

    shared_loan_installments = fields.Integer(
        string="Cuotas (solo si la plantilla es préstamo)",
        default=0,
        help="0 = usar las cuotas de la plantilla. Si indica un número, sustituye las cuotas al asignar.",
    )
    assign_installments_preview = fields.Integer(
        string="Cuotas calculadas",
        compute="_compute_assign_installments_preview",
        help="Para conceptos no préstamo con fecha fin: períodos según quincena. Sin fecha fin: 1.",
    )
    preview_employee_count = fields.Integer(
        string="Empleados en ámbito",
        compute="_compute_assign_preview",
    )
    preview_will_create_count = fields.Integer(
        string="Líneas a crear",
        compute="_compute_assign_preview",
    )
    preview_skip_duplicate_count = fields.Integer(
        string="Omitidos (código duplicado)",
        compute="_compute_assign_preview",
    )
    preview_skip_structure_count = fields.Integer(
        string="Omitidos (estructura)",
        compute="_compute_assign_preview",
    )
    preview_employee_sample = fields.Char(
        string="Muestra de empleados",
        compute="_compute_assign_preview",
    )
    preview_warning_html = fields.Html(
        string="Advertencias",
        compute="_compute_assign_preview",
        sanitize=False,
    )

    inline_code = fields.Char(string="Código", help="Requerido en modo definir aquí.")
    inline_name = fields.Char(string="Nombre / descripción")
    inline_concept_type = fields.Selection(
        [("income", "Ingreso"), ("deduction", "Deducción")],
        string="Tipo de concepto",
        default="deduction",
    )
    inline_amount_type = fields.Selection(
        [("fixed", "Monto fijo"), ("percentage", "Porcentaje")],
        string="Tipo de monto",
        default="fixed",
    )
    inline_structure_type_ids = fields.Many2many(
        "hr.payroll.structure.type",
        "gn_hr_assign_wiz_stype_rel",
        "wiz_id",
        "stype_id",
        string="Tipos de nómina permitidos",
        help="Vacío: sin filtro por tipo de estructura.",
    )
    for_payroll = fields.Boolean(
        string="Para nómina",
        default=False,
        help="Al copiar desde plantilla se hereda; en definir aquí puede activarlo.",
    )

    inline_is_loan = fields.Boolean(string="Es préstamo")
    inline_installments = fields.Integer(string="Cuotas (préstamo)", default=1)
    initial_paid_installments = fields.Integer(
        string="Cuotas ya pagadas (préstamo)",
        default=0,
        help="Para préstamos en curso: cuotas ya descontadas antes de esta asignación.",
    )

    available_concept_ids = fields.Many2many(
        "hr.employee.recurring.concept",
        compute="_compute_available_concepts",
    )

    unassign_match = fields.Selection(
        [
            ("shared_template", "Misma plantilla (código de la plantilla)"),
            ("code", "Por código"),
        ],
        string="Cómo identificar el concepto",
        default="code",
    )
    unassign_template_id = fields.Many2one(
        "hr.employee.recurring.concept",
        string="Plantilla a retirar",
        domain="[('employee_id', '=', False), ('is_template', '=', True), ('active', '=', True)]",
        help="Desactiva en empleados las líneas activas con el mismo código.",
    )
    unassign_code = fields.Char(string="Código a desasignar")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context or {}
        cid = ctx.get("default_concept_id")
        if cid:
            concept = self.env["hr.employee.recurring.concept"].browse(cid)
            res["concept_id"] = concept.id
            res["source_mode"] = "shared"
            res["concept_id_locked"] = True
            res["assign_amount"] = concept.amount
            res["assign_apply_biweek"] = concept.apply_biweek or "both"
            res["loan_split_quota_across_biweeks"] = bool(
                concept.loan_split_quota_across_biweeks
            )
            if concept.is_loan:
                res["loan_first_biweek_amount"] = concept.loan_first_biweek_amount
                res["first_quota_differentiated"] = bool(concept.first_quota_differentiated)
                res["first_quota_amount"] = concept.first_quota_amount or 0.0
            else:
                res["loan_first_biweek_amount"] = concept.loan_first_biweek_amount
                res["first_quota_differentiated"] = False
                res["first_quota_amount"] = 0.0
            res["date_start"] = concept.date_start or fields.Date.context_today(self)
            res["date_end"] = concept.date_end
            res["for_payroll"] = concept.for_payroll
            res["shared_loan_installments"] = 0
        return res

    @api.onchange("assign_apply_biweek")
    def _onchange_assign_apply_biweek_clear_split(self):
        for w in self:
            if w.assign_apply_biweek != "both":
                w.loan_split_quota_across_biweeks = False

    @api.onchange("concept_id", "source_mode")
    def _onchange_concept_id_loan_first_biweek(self):
        for w in self:
            if w.source_mode != "shared" or not w.concept_id or not w.concept_id.is_loan:
                continue
            w.loan_first_biweek_amount = w.concept_id.loan_first_biweek_amount
            w.first_quota_differentiated = bool(w.concept_id.first_quota_differentiated)
            w.first_quota_amount = w.concept_id.first_quota_amount or 0.0

    @api.onchange("company_id")
    def _onchange_company_id_scope(self):
        for w in self:
            if not w.company_id:
                continue
            if w.department_ids:
                w.department_ids = w.department_ids.filtered(
                    lambda d: d.company_id == w.company_id
                )
            if w.employee_ids:
                w.employee_ids = w.employee_ids.filtered(
                    lambda e: e.company_id == w.company_id
                )

    @api.depends("company_id")
    def _compute_available_concepts(self):
        Rec = self.env["hr.employee.recurring.concept"]
        for w in self:
            dom = [
                ("employee_id", "=", False),
                ("is_template", "=", True),
                ("active", "=", True),
            ]
            if w.company_id:
                dom.append(("company_id", "=", w.company_id.id))
            w.available_concept_ids = Rec.search(dom)

    @api.depends(
        "source_mode",
        "inline_is_loan",
        "inline_installments",
        "date_start",
        "date_end",
        "assign_apply_biweek",
        "concept_id",
        "concept_id.is_loan",
        "shared_loan_installments",
    )
    def _compute_assign_installments_preview(self):
        Rec = self.env["hr.employee.recurring.concept"]
        for w in self:
            if w.source_mode == "shared" and w.concept_id and w.concept_id.is_loan:
                inst = w.shared_loan_installments or w.concept_id.installments or 1
                w.assign_installments_preview = max(1, inst)
            elif w.source_mode == "inline" and w.inline_is_loan:
                w.assign_installments_preview = max(1, w.inline_installments or 1)
            elif not w.date_end:
                w.assign_installments_preview = 1
            else:
                w.assign_installments_preview = Rec.count_application_periods(
                    w.date_start, w.date_end, w.assign_apply_biweek
                )

    @api.depends(
        "wizard_type",
        "company_id",
        "assignment_scope",
        "department_ids",
        "employee_ids",
        "source_mode",
        "concept_id",
        "concept_id.is_loan",
        "inline_code",
        "inline_is_loan",
        "assign_amount",
        "shared_loan_installments",
        "inline_installments",
    )
    def _compute_assign_preview(self):
        for w in self:
            w.preview_employee_count = 0
            w.preview_will_create_count = 0
            w.preview_skip_duplicate_count = 0
            w.preview_skip_structure_count = 0
            w.preview_employee_sample = ""
            w.preview_warning_html = False
            if w.wizard_type != "assign":
                continue
            stats = w._gather_assign_preview()
            w.preview_employee_count = stats["employee_count"]
            w.preview_will_create_count = stats["will_create"]
            w.preview_skip_duplicate_count = stats["skip_duplicate"]
            w.preview_skip_structure_count = stats["skip_structure"]
            w.preview_employee_sample = stats["sample_names"]
            if stats["warnings"]:
                w.preview_warning_html = "<ul>%s</ul>" % "".join(
                    f"<li>{line}</li>" for line in stats["warnings"]
                )

    def _gather_assign_preview(self):
        self.ensure_one()
        empty = {
            "employee_count": 0,
            "will_create": 0,
            "skip_duplicate": 0,
            "skip_structure": 0,
            "sample_names": "",
            "warnings": [],
        }
        try:
            employees = self._get_target_employees()
        except UserError:
            return empty
        if not employees:
            return empty
        assign_code = ""
        warnings = []
        if self.source_mode == "shared":
            if not self.concept_id:
                warnings.append(_("Seleccione una plantilla del catálogo."))
            else:
                assign_code = (self.concept_id.code or "").strip()
                if self.concept_id.is_loan and not (
                    self.shared_loan_installments or self.concept_id.installments
                ):
                    warnings.append(_("La plantilla de préstamo no tiene cuotas definidas."))
        else:
            assign_code = (self.inline_code or "").strip()
            if not assign_code:
                warnings.append(_("Indique el código en modo «Definir aquí»."))
            if self.inline_is_loan and not (self.inline_installments or 0):
                warnings.append(_("Indique el número de cuotas del préstamo."))
        if not assign_code and not warnings:
            warnings.append(_("No se pudo determinar el código del concepto."))

        structure_types = self._structure_filter_record()
        Concept = self.env["hr.employee.recurring.concept"]
        will_create = 0
        skip_duplicate = 0
        skip_structure = 0
        create_names = []
        for emp in employees:
            if not self._employee_matches_structure_types(emp, structure_types):
                skip_structure += 1
                continue
            if assign_code and Concept.search(
                [
                    ("employee_id", "=", emp.id),
                    ("active", "=", True),
                    ("code", "=", assign_code),
                ],
                limit=1,
            ):
                skip_duplicate += 1
                continue
            will_create += 1
            if len(create_names) < 8:
                create_names.append(emp.name)

        sample = ", ".join(create_names)
        if will_create > len(create_names):
            sample = _("%(names)s y %(more)d más") % {
                "names": sample,
                "more": will_create - len(create_names),
            }
        if will_create == 0 and not warnings:
            warnings.append(_("Ningún empleado recibirá una línea nueva con los criterios actuales."))
        if self.assign_amount == 0 and not (
            self.source_mode == "shared"
            and self.concept_id
            and self.concept_id.amount_type == "percentage"
        ):
            warnings.append(_("El monto asignado es 0."))

        return {
            "employee_count": len(employees),
            "will_create": will_create,
            "skip_duplicate": skip_duplicate,
            "skip_structure": skip_structure,
            "sample_names": sample,
            "warnings": warnings,
        }

    def _get_target_employees_domain(self):
        self.ensure_one()
        dom = Domain("company_id", "=", self.company_id.id)
        if self.assignment_scope == "departments":
            if not self.department_ids:
                raise UserError(_("Seleccione al menos un departamento."))
            dom = dom & Domain("department_id", "in", self.department_ids.ids)
        elif self.assignment_scope == "employees":
            if not self.employee_ids:
                raise UserError(_("Seleccione al menos un empleado."))
            dom = dom & Domain("id", "in", self.employee_ids.ids)
        return dom

    def _get_target_employees(self):
        self.ensure_one()
        return self.env["hr.employee"].search(self._get_target_employees_domain())

    def _employee_matches_structure_types(self, employee, structure_type_ids):
        if not structure_type_ids:
            return True
        v_sudo = employee.current_version_id.sudo() if employee.current_version_id else False
        if v_sudo and v_sudo.structure_type_id:
            return v_sudo.structure_type_id.id in structure_type_ids.ids
        return not structure_type_ids

    def _template_vals(self):
        self.ensure_one()
        if self.source_mode != "shared" or not self.concept_id:
            return {}
        c = self.concept_id
        return {
            "name_from_concept_id": c.id,
            "name": c.name,
            "code": c.code,
            "concept_type": c.concept_type,
            "amount_type": c.amount_type,
            "structure_type_ids": [(6, 0, c.structure_type_ids.ids)],
            "is_loan": c.is_loan,
            "for_payroll": c.for_payroll,
        }

    def _computed_installments_assign(self):
        self.ensure_one()
        Rec = self.env["hr.employee.recurring.concept"]
        if self.source_mode == "shared" and self.concept_id and self.concept_id.is_loan:
            inst = self.shared_loan_installments or self.concept_id.installments or 1
            return max(1, inst)
        if self.source_mode == "inline" and self.inline_is_loan:
            return max(1, self.inline_installments or 1)
        if not self.date_end:
            return 1
        return Rec.count_application_periods(
            self.date_start, self.date_end, self.assign_apply_biweek
        )

    def _inline_vals_base(self):
        self.ensure_one()
        if self.source_mode != "inline":
            return {}
        code = (self.inline_code or "").strip()
        if not code:
            raise UserError(_("En modo «Definir aquí» debe indicar el código del concepto."))
        structure_cmds = (
            [(6, 0, self.inline_structure_type_ids.ids)] if self.inline_structure_type_ids else [(5, 0, 0)]
        )
        is_loan = self.inline_is_loan
        installments = self._computed_installments_assign()
        return {
            "name_from_concept_id": False,
            "code": code,
            "name": (self.inline_name or code).strip() or code,
            "concept_type": self.inline_concept_type,
            "amount_type": self.inline_amount_type,
            "structure_type_ids": structure_cmds,
            "is_loan": is_loan,
            "installments": installments,
            "initial_paid_installments": self.initial_paid_installments if is_loan else 0,
            "for_payroll": self.for_payroll,
        }

    def _assign_code(self):
        self.ensure_one()
        if self.source_mode == "shared":
            return (self.concept_id.code or "").strip() if self.concept_id else ""
        return (self.inline_code or "").strip()

    def _structure_filter_record(self):
        self.ensure_one()
        if self.source_mode == "shared" and self.concept_id:
            return self.concept_id.structure_type_ids
        if self.source_mode == "inline":
            return self.inline_structure_type_ids
        return self.env["hr.payroll.structure.type"]

    def action_assign(self):
        self.ensure_one()
        if self.wizard_type != "assign":
            raise UserError(_("Use el botón correspondiente al tipo de operación."))

        employees = self._get_target_employees()
        if not employees:
            raise UserError(
                _("No hay empleados que coincidan con la compañía y el filtro seleccionado.")
            )

        if self.source_mode == "shared":
            if not self.concept_id:
                raise UserError(_("Debe seleccionar un concepto del catálogo (plantilla)."))
        else:
            self._inline_vals_base()

        assign_code = self._assign_code()
        if not assign_code:
            raise UserError(_("No se pudo determinar el código del concepto a asignar."))

        structure_types = self._structure_filter_record()
        Concept = self.env["hr.employee.recurring.concept"]
        installments_non_loan = self._computed_installments_assign()

        created = 0
        for emp in employees:
            if not self._employee_matches_structure_types(emp, structure_types):
                continue

            same = Concept.search(
                [
                    ("employee_id", "=", emp.id),
                    ("active", "=", True),
                    ("code", "=", assign_code),
                ],
                limit=1,
            )
            if same:
                _logger.info(
                    "Skip mass assign: employee %s already has recurring concept code %s",
                    emp.id,
                    assign_code,
                )
                continue

            vals = {
                "employee_id": emp.id,
                "company_id": self.company_id.id,
                "is_template": False,
                "date_start": self.date_start,
                "date_end": self.date_end if self.date_end else False,
                "apply_biweek": self.assign_apply_biweek,
                "amount": self.assign_amount,
            }
            if self.source_mode == "shared":
                vals.update(self._template_vals())
                if not self.concept_id.is_loan:
                    vals["installments"] = installments_non_loan
                else:
                    vals["installments"] = installments_non_loan
                    vals["initial_paid_installments"] = self.initial_paid_installments
            else:
                vals.update(self._inline_vals_base())
                if not self.inline_is_loan:
                    vals["installments"] = installments_non_loan

            vals["loan_split_quota_across_biweeks"] = bool(
                self.loan_split_quota_across_biweeks
            )
            vals["loan_first_biweek_amount"] = self.loan_first_biweek_amount or 0.0
            if vals.get("is_loan"):
                vals["first_quota_differentiated"] = bool(self.first_quota_differentiated)
                vals["first_quota_amount"] = float(self.first_quota_amount or 0.0)
            else:
                vals["first_quota_differentiated"] = False
                vals["first_quota_amount"] = 0.0

            Concept.create(vals)
            created += 1

        if not created:
            raise UserError(
                _(
                    "No se creó ninguna línea. Revise la vista previa: puede haber duplicados "
                    "por código o empleados fuera del tipo de estructura."
                )
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Asignación completada"),
                "message": _("%(count)d concepto(s) recurrente(s) creado(s).") % {
                    "count": created
                },
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_unassign(self):
        self.ensure_one()
        if self.wizard_type != "unassign":
            raise UserError(_("Use el botón correspondiente al tipo de operación."))

        employees = self._get_target_employees()
        if not employees:
            raise UserError(
                _("No hay empleados que coincidan con la compañía y el filtro seleccionado.")
            )

        if self.unassign_match == "shared_template":
            if not self.unassign_template_id:
                raise UserError(_("Seleccione la plantilla cuyo código debe retirarse de los empleados."))
            code = (self.unassign_template_id.code or "").strip()
        else:
            code = (self.unassign_code or "").strip()

        if not code:
            raise UserError(_("Indique el código del concepto a desasignar."))

        Rec = self.env["hr.employee.recurring.concept"]
        lines = Rec.search(
            [
                ("employee_id", "in", employees.ids),
                ("code", "=", code),
                ("active", "=", True),
            ]
        )
        if lines:
            lines.write({"active": False})

        return {"type": "ir.actions.act_window_close"}
