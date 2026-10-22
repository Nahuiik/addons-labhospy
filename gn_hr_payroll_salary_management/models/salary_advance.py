# -*- coding: utf-8 -*-
# © 2025–2026 Grupo Nahuiik

from calendar import monthrange
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SalaryAdvance(models.Model):
    """Salary advance requests with approval workflow (country-specific limits via extension)."""
    _name = "salary.advance"
    _description = "Salary Advance"
    _order = "date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )

    date = fields.Date(string="Request Date", required=True, default=fields.Date.today, tracking=True)

    advance_target = fields.Selection(
        [
            ("payroll", "Salario (planilla)"),
        ],
        string="Tipo de anticipo",
        required=True,
        default="payroll",
        tracking=True,
        ondelete={"payroll": "set default"},
    )

    advance_amount = fields.Float(string="Advance Amount", digits=(12, 2), required=True, tracking=True)

    recurring_concept_id = fields.Many2one(
        "hr.employee.recurring.concept",
        string="Deducción recurrente",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    current_wage = fields.Float(
        string="Current Monthly Wage",
        digits=(12, 2),
        compute="_compute_current_wage",
        store=False,
    )

    max_advance_percentage = fields.Float(
        string="Max Advance %",
        digits=(5, 2),
        compute="_compute_max_advance",
        store=False,
    )

    max_advance_amount = fields.Float(
        string="Max Advance Amount",
        digits=(12, 2),
        compute="_compute_max_advance",
        store=False,
    )
    max_advance_reference_amount = fields.Float(
        string="Base del tope (anticipo)",
        digits=(12, 2),
        compute="_compute_max_advance",
        store=False,
    )
    max_advance_base_note = fields.Char(
        string="Origen base tope",
        compute="_compute_max_advance",
        store=False,
    )

    advance_percentage = fields.Float(
        string="Advance %",
        digits=(5, 2),
        compute="_compute_advance_percentage",
        store=False,
    )

    min_days_since_payment = fields.Integer(
        string="Min Days Since Payment",
        compute="_compute_min_days",
        store=False,
    )
    days_since_last_payment = fields.Integer(
        string="Days Since Last Payment",
        compute="_compute_days_since_payment",
        store=False,
    )

    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        check_company=True,
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank', 'cash'))]",
    )
    debit_account_id = fields.Many2one(
        "account.account",
        string="Debit Account",
        check_company=True,
    )
    credit_account_id = fields.Many2one(
        "account.account",
        string="Credit Account",
        check_company=True,
    )
    move_id = fields.Many2one("account.move", string="Accounting Entry", readonly=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submit", "Submitted"),
            ("waiting_approval", "Waiting Approval"),
            ("approved", "Approved"),
            ("cancel", "Cancelled"),
            ("reject", "Rejected"),
        ],
        string="State",
        default="draft",
        required=True,
        tracking=True,
    )

    notes = fields.Text(string="Notes")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        cid = vals.get("company_id")
        company = self.env["res.company"].browse(cid) if cid else self.env.company
        if company:
            if "journal_id" in fields_list and not vals.get("journal_id") and company.salary_advance_journal_id:
                vals["journal_id"] = company.salary_advance_journal_id.id
            if "debit_account_id" in fields_list and not vals.get("debit_account_id") and company.salary_advance_debit_account_id:
                vals["debit_account_id"] = company.salary_advance_debit_account_id.id
            if "credit_account_id" in fields_list and not vals.get("credit_account_id") and company.salary_advance_credit_account_id:
                vals["credit_account_id"] = company.salary_advance_credit_account_id.id
        return vals

    @api.onchange("company_id")
    def _onchange_company_id_advance_accounting(self):
        if not self.company_id:
            return
        c = self.company_id
        if c.salary_advance_journal_id:
            self.journal_id = c.salary_advance_journal_id
        if c.salary_advance_debit_account_id:
            self.debit_account_id = c.salary_advance_debit_account_id
        if c.salary_advance_credit_account_id:
            self.credit_account_id = c.salary_advance_credit_account_id

    def _require_accounting_for_payment(self):
        self.ensure_one()
        if not self.journal_id or not self.debit_account_id or not self.credit_account_id:
            raise UserError(_(
                "Debe indicar el diario (banco o efectivo) y las cuentas contables del anticipo, "
                "o configurar los valores predeterminados en Ajustes → Nómina → Anticipos salariales."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        seq_env = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = seq_env.next_by_code("salary.advance") or _("New")
        return super().create(vals_list)

    @api.depends("employee_id")
    def _compute_current_wage(self):
        for rec in self:
            if rec.employee_id and rec.employee_id.current_version_id:
                rec.current_wage = rec.employee_id.current_version_id.wage or 0.0
            else:
                rec.current_wage = 0.0

    @api.depends(
        "employee_id",
        "date",
        "advance_target",
        "employee_id.current_version_id",
        "employee_id.current_version_id.wage",
        "employee_id.current_version_id.schedule_pay",
        "employee_id.current_version_id.structure_type_id",
        "employee_id.current_version_id.structure_type_id.max_advance_percentage",
        "employee_id.current_version_id.structure_type_id.advance_max_base",
        "employee_id.recurring_concept_ids",
        "employee_id.recurring_concept_ids.active",
        "employee_id.recurring_concept_ids.concept_type",
        "employee_id.recurring_concept_ids.amount",
        "employee_id.recurring_concept_ids.amount_type",
        "employee_id.recurring_concept_ids.is_loan",
        "employee_id.recurring_concept_ids.paid_installments",
        "employee_id.recurring_concept_ids.installments",
        "employee_id.recurring_concept_ids.apply_biweek",
        "employee_id.recurring_concept_ids.loan_split_quota_across_biweeks",
        "employee_id.recurring_concept_ids.loan_first_biweek_amount",
        "employee_id.recurring_concept_ids.date_start",
        "employee_id.recurring_concept_ids.company_id",
    )
    def _compute_max_advance(self):
        for rec in self:
            if rec.employee_id:
                ref_d = rec.date or fields.Date.context_today(rec)
                lim = rec._advance_limit_values(
                    rec.employee_id, ref_d, rec.advance_target or "payroll")
                rec.max_advance_percentage = lim["max_advance_percentage"]
                rec.max_advance_reference_amount = lim["max_advance_reference_amount"]
                rec.max_advance_base_note = lim["max_advance_base_note"]
                rec.max_advance_amount = lim["max_advance_amount"]
            else:
                rec.max_advance_percentage = 0.0
                rec.max_advance_reference_amount = 0.0
                rec.max_advance_base_note = ""
                rec.max_advance_amount = 0.0

    @api.model
    def _period_gross_from_monthly_wage(self, monthly_wage, periodicity):
        w = monthly_wage or 0.0
        p = periodicity or "monthly"
        if p in ("biweekly", "bi-weekly"):
            return w / 2.0
        if p == "weekly":
            return w / 4.33
        return w

    @api.model
    def _periodicity_from_structure_type(self, structure_type):
        if not structure_type or not structure_type.default_schedule_pay:
            return "monthly"
        sched = structure_type.default_schedule_pay
        return {
            "weekly": "weekly",
            "bi-weekly": "biweekly",
            "biweekly": "biweekly",
            "monthly": "monthly",
        }.get(sched, "monthly")

    @api.model
    def _periodicity_from_version(self, version):
        """Usa periodicidad de localización si existe; si no, deriva de schedule_pay estándar."""
        if not version:
            return "monthly"
        loc = getattr(version, "periodicity", None)
        if loc:
            return loc
        sched = getattr(version, "schedule_pay", None) or "monthly"
        return {
            "weekly": "weekly",
            "bi-weekly": "biweekly",
            "biweekly": "biweekly",
            "monthly": "monthly",
        }.get(sched, "monthly")

    @api.model
    def _structure_type_for_advance_target(self, advance_target, employee):
        """Override in localization (13°/14°, aguinaldo, etc.)."""
        if employee and employee.current_version_id:
            return employee.current_version_id.structure_type_id
        return self.env["hr.payroll.structure.type"].browse()

    @api.model
    def _supplement_pay_gross_and_periodicity(self, employee, advance_target, ref_date):
        """Return (monthly_wage, periodicity) for non-regular targets, or None."""
        return None

    @api.model
    def _payslip_period_bounds(self, ref_date, periodicity):
        if not ref_date:
            ref_date = fields.Date.context_today(self)
        else:
            ref_date = fields.Date.to_date(ref_date)
        y, m, d = ref_date.year, ref_date.month, ref_date.day
        p = periodicity or "monthly"
        if p in ("biweekly", "bi-weekly"):
            if d <= 15:
                return date(y, m, 1), date(y, m, 15)
            last = date(y, m, monthrange(y, m)[1])
            return date(y, m, 16), last
        if p == "weekly":
            start = ref_date - timedelta(days=ref_date.weekday())
            end = start + timedelta(days=6)
            return start, end
        last = date(y, m, monthrange(y, m)[1])
        return date(y, m, 1), last

    @api.model
    def _recurring_deductions_total_for_period(self, employee, ref_date=None, periodicity_for_limit=None):
        if not employee or not employee.current_version_id:
            return 0.0
        ref_date = ref_date or fields.Date.context_today(self)
        ver = employee.current_version_id
        periodicity = (
            periodicity_for_limit if periodicity_for_limit is not None else self._periodicity_from_version(ver)
        )
        period_gross = self._period_gross_from_monthly_wage(ver.wage or 0.0, periodicity)
        period_start, period_end = self._payslip_period_bounds(ref_date, periodicity)

        Concept = self.env["hr.employee.recurring.concept"]
        concepts = Concept.search([
            ("employee_id", "=", employee.id),
            ("active", "=", True),
            ("concept_type", "=", "deduction"),
        ])
        total = 0.0
        for concept in concepts:
            if concept.date_start and concept.date_start > period_end:
                continue
            if concept.date_end and concept.date_end < period_start:
                continue
            if concept.is_loan and concept.installments and concept.paid_installments >= concept.installments:
                continue
            if periodicity == "biweekly" and concept.apply_biweek and concept.apply_biweek != "both":
                is_first_half = ref_date.day <= 15
                if concept.apply_biweek == "first" and not is_first_half:
                    continue
                if concept.apply_biweek == "second" and is_first_half:
                    continue
            if concept.amount_type == "fixed":
                amt = concept.amount or 0.0
            elif concept.amount_type == "percentage":
                amt = period_gross * ((concept.amount or 0.0) / 100.0)
            else:
                amt = 0.0
            amt = concept._gn_effective_recurring_deduction_base(amt)
            amt = concept._gn_apply_loan_biweek_split_to_amount(amt, employee, ref_date)
            if amt > 0:
                total += amt
        return total

    @api.model
    def _legal_retentions_period_estimate(self, employee, ref_date=None, periodicity_for_limit=None):
        """Override in localization (IHSS, ISR, etc.). Base: no estimate."""
        return 0.0

    @api.model
    def _contract_period_net_estimate(self, employee, ref_date=None, advance_target="payroll"):
        if not employee or not employee.current_version_id:
            return 0.0
        ref_date = ref_date or fields.Date.context_today(self)
        ver = employee.current_version_id
        supplement = self._supplement_pay_gross_and_periodicity(employee, advance_target, ref_date)
        if supplement:
            monthly_wage, lim_per = supplement
            period_gross = self._period_gross_from_monthly_wage(monthly_wage, lim_per)
            recurring = self._recurring_deductions_total_for_period(
                employee, ref_date, periodicity_for_limit=lim_per)
            legal = self._legal_retentions_period_estimate(
                employee, ref_date, periodicity_for_limit=lim_per)
        else:
            period_gross = self._period_gross_from_monthly_wage(
                ver.wage or 0.0, self._periodicity_from_version(ver))
            recurring = self._recurring_deductions_total_for_period(employee, ref_date)
            legal = self._legal_retentions_period_estimate(employee, ref_date)
        return max(0.0, period_gross - recurring - legal)

    @api.model
    def _advance_reference_amount_and_note(self, employee, ref_date=None, advance_target="payroll"):
        if not employee or not employee.current_version_id:
            return 0.0, ""
        ref_date = ref_date or fields.Date.context_today(self)
        limit_st = self._structure_type_for_advance_target(advance_target, employee)
        contract_base = self._contract_period_net_estimate(employee, ref_date, advance_target)
        if not limit_st:
            return contract_base, _(
                "Neto estimado del período (bruto − deducciones recurrentes y retenciones estimadas)"
            )
        if limit_st.advance_max_base != "last_payslip_net":
            return contract_base, _(
                "Bruto del período menos deducciones recurrentes y retenciones estimadas "
                "(según tipo de estructura del anticipo)"
            )
        net_amt = self._net_total_from_last_payslip_for_structure_type(employee, limit_st)
        if net_amt > 0:
            return net_amt, _("Neto de la última nómina de este tipo (línea NET)")
        if contract_base > 0:
            return contract_base, _("Sin recibo NET previo de este tipo; neto estimado del contrato")
        return 0.0, _("Sin dato de contrato ni nómina")

    @api.model
    def _advance_limit_values(self, employee, ref_date=None, advance_target="payroll"):
        percentage = 0.0
        ref_amount = 0.0
        note = ""
        max_amount = 0.0
        if employee and employee.current_version_id:
            ref_amount, note = self._advance_reference_amount_and_note(
                employee, ref_date, advance_target)
            limit_st = self._structure_type_for_advance_target(advance_target, employee)
            percentage = (limit_st.max_advance_percentage or 0.0) if limit_st else 0.0
            if percentage > 0 and ref_amount > 0:
                max_amount = ref_amount * (percentage / 100.0)
        return {
            "max_advance_percentage": percentage,
            "max_advance_reference_amount": ref_amount,
            "max_advance_amount": max_amount,
            "max_advance_base_note": note,
        }

    @api.model
    def _net_total_from_last_payslip_for_structure_type(self, employee, structure_type):
        if not employee or not structure_type:
            return 0.0
        struct = structure_type.default_struct_id
        if not struct:
            return 0.0
        payslip = self.env["hr.payslip"].search([
            ("employee_id", "=", employee.id),
            ("state", "=", "done"),
            ("struct_id", "=", struct.id),
        ], order="date_to desc", limit=1)
        if not payslip:
            return 0.0
        net_lines = payslip.line_ids.filtered(lambda l: l.code == "NET")
        if not net_lines:
            return 0.0
        return abs(net_lines[0].total or 0.0)

    @api.depends(
        "advance_amount",
        "current_wage",
        "max_advance_reference_amount",
        "advance_target",
        "employee_id",
        "employee_id.current_version_id",
        "employee_id.current_version_id.schedule_pay",
        "employee_id.current_version_id.wage",
    )
    def _compute_advance_percentage(self):
        for rec in self:
            base = rec.max_advance_reference_amount or 0.0
            if not base and rec.employee_id and rec.employee_id.current_version_id:
                ver = rec.employee_id.current_version_id
                base = rec._period_gross_from_monthly_wage(
                    ver.wage or 0.0, rec._periodicity_from_version(ver))
            if not base:
                base = rec.current_wage or 0.0
            if base > 0:
                rec.advance_percentage = (rec.advance_amount / base) * 100.0
            else:
                rec.advance_percentage = 0.0

    @api.depends("employee_id", "advance_target")
    def _compute_min_days(self):
        for rec in self:
            min_days = 0
            if rec.employee_id:
                st = self._structure_type_for_advance_target(
                    rec.advance_target, rec.employee_id)
                if st:
                    min_days = st.min_days_advance or 0
            rec.min_days_since_payment = min_days

    @api.depends("employee_id", "date", "advance_target")
    def _compute_days_since_payment(self):
        for rec in self:
            days = 0
            if rec.employee_id:
                st = self._structure_type_for_advance_target(
                    rec.advance_target, rec.employee_id)
                struct = st.default_struct_id if st else False
                domain = [
                    ("employee_id", "=", rec.employee_id.id),
                    ("state", "=", "done"),
                ]
                last_payslip = self.env["hr.payslip"].browse()
                if struct:
                    last_payslip = self.env["hr.payslip"].search(
                        domain + [("struct_id", "=", struct.id)],
                        order="date_to desc", limit=1,
                    )
                if not last_payslip:
                    last_payslip = self.env["hr.payslip"].search(
                        domain, order="date_to desc", limit=1)
                if last_payslip and last_payslip.date_to:
                    delta = rec.date - last_payslip.date_to
                    days = delta.days
            rec.days_since_last_payment = days

    @api.constrains("employee_id")
    def _check_employee_contract(self):
        for rec in self:
            if rec.employee_id and not rec.employee_id.current_version_id:
                raise ValidationError(_("El empleado debe tener un contrato activo."))

    @api.constrains("employee_id")
    def _check_employee_address(self):
        for rec in self:
            if rec.employee_id:
                if not rec.employee_id.work_contact_id or not rec.employee_id.work_contact_id.street:
                    raise ValidationError(_("El empleado debe tener una dirección configurada."))

    @api.constrains("advance_amount", "max_advance_amount")
    def _check_advance_amount(self):
        for rec in self:
            if rec.max_advance_amount > 0 and float_compare(
                rec.advance_amount, rec.max_advance_amount, precision_digits=2
            ) > 0:
                raise ValidationError(
                    _("El monto del anticipo (%.2f) excede el máximo permitido (%.2f).")
                    % (rec.advance_amount, rec.max_advance_amount)
                )

    @api.constrains("days_since_last_payment", "min_days_since_payment")
    def _check_min_days(self):
        for rec in self:
            if rec.min_days_since_payment > 0 and rec.days_since_last_payment < rec.min_days_since_payment:
                raise ValidationError(
                    _("Deben pasar al menos %d días desde el último pago. Han pasado %d días.")
                    % (rec.min_days_since_payment, rec.days_since_last_payment)
                )

    def _payslip_input_code(self):
        """Override in localization for voucher-specific input codes."""
        self.ensure_one()
        ver = self.employee_id.current_version_id
        if ver and self._periodicity_from_version(ver) == "biweekly":
            return "ADV_BIWEEKLY_SALARY"
        return "AS"

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("El anticipo ya está en borrador."))
        if self.state == "cancel":
            raise UserError(_("No se puede volver a borrador un anticipo cancelado."))

        if self.state == "approved":
            self._reset_approved_to_draft()
            self.message_post(body=_(
                "Anticipo aprobado revertido: asiento extornado, deducción eliminada si aplica; regresado a borrador."
            ))
            return

        if self.state not in ("submit", "waiting_approval", "reject"):
            raise UserError(_(
                "Solo se puede regresar a borrador desde «Enviado», «En espera de aprobación», "
                "«Rechazado» o «Aprobado»."
            ))
        self.state = "draft"
        self.message_post(body=_("Solicitud regresada a borrador."))

    def _reset_approved_to_draft(self):
        self.ensure_one()
        if self.state != "approved":
            return

        concept = self.recurring_concept_id
        if concept and concept.paid_installments > 0:
            raise UserError(_(
                "No se puede volver a borrador: la deducción recurrente del anticipo ya tiene cuotas "
                "marcadas como pagadas. Revise la nómina o el concepto antes de revertir."
            ))

        move = self.move_id
        if move:
            if move.state == "posted":
                move._reverse_moves(cancel=True)
            elif move.state == "draft":
                move.button_cancel()

        if concept:
            self.recurring_concept_id = False
            concept.unlink()

        self.write({
            "move_id": False,
            "state": "draft",
        })

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Solo se pueden enviar anticipos en estado borrador."))

        self._check_advance_amount()
        self._check_min_days()
        self._require_accounting_for_payment()

        self.state = "submit"
        self.message_post(body=_("Anticipo enviado para aprobación."))

    def action_approve(self):
        self.ensure_one()
        if self.state == "approved":
            raise UserError(_("Este anticipo ya está aprobado."))
        if self.state in ("cancel", "reject"):
            raise UserError(_("No se puede aprobar un anticipo cancelado o rechazado."))
        if self.state not in ("draft", "submit", "waiting_approval"):
            raise UserError(
                _("No se puede aprobar en el estado «%s». Solo borrador, enviado o en espera de aprobación.")
                % dict(self._fields["state"].selection).get(self.state, self.state)
            )

        self._check_advance_amount()
        self._check_min_days()
        self._require_accounting_for_payment()

        move_vals = {
            "date": self.date,
            "journal_id": self.journal_id.id,
            "ref": _("Anticipo Salarial: %s") % self.name,
            "line_ids": [
                (0, 0, {
                    "account_id": self.debit_account_id.id,
                    "debit": self.advance_amount,
                    "credit": 0.0,
                    "partner_id": self.employee_id.work_contact_id.id if self.employee_id.work_contact_id else False,
                    "name": _("Anticipo Salarial - %s") % self.employee_id.name,
                }),
                (0, 0, {
                    "account_id": self.credit_account_id.id,
                    "debit": 0.0,
                    "credit": self.advance_amount,
                    "partner_id": self.employee_id.work_contact_id.id if self.employee_id.work_contact_id else False,
                    "name": _("Anticipo Salarial - %s") % self.employee_id.name,
                }),
            ],
        }

        move = self.env["account.move"].create(move_vals)
        move.action_post()

        self.move_id = move.id
        self.state = "approved"
        self.message_post(body=_("Anticipo aprobado y contabilizado."))

        self._create_advance_deduction()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Anticipo Aprobado"),
                "message": _("El anticipo ha sido aprobado y contabilizado. Se creó una deducción recurrente."),
                "type": "success",
            },
        }

    def _create_advance_deduction(self):
        self.ensure_one()
        if not self.employee_id:
            return
        if self.recurring_concept_id:
            return

        code = self._payslip_input_code()
        labels = dict(self._fields["advance_target"].selection)
        name = _("Anticipo %(kind)s — %(ref)s") % {
            "kind": labels.get(self.advance_target, ""),
            "ref": self.name,
        }
        concept = self.env["hr.employee.recurring.concept"].create({
            "employee_id": self.employee_id.id,
            "name": name,
            "code": code,
            "concept_type": "deduction",
            "amount_type": "fixed",
            "amount": self.advance_amount,
            "is_loan": True,
            "total_amount": self.advance_amount,
            "installments": 1,
            "date_start": self.date,
            "active": True,
            "salary_advance_id": self.id,
        })
        self.recurring_concept_id = concept.id

    def action_cancel(self):
        self.ensure_one()
        if self.state == "approved":
            raise UserError(_(
                "No se puede cancelar un anticipo aprobado. Debe revertir el asiento contable primero."
            ))

        self.state = "cancel"
        self.message_post(body=_("Anticipo cancelado."))

    def action_reject(self):
        self.ensure_one()
        if self.state not in ("submit", "waiting_approval"):
            raise UserError(_("Solo se pueden rechazar anticipos enviados."))

        self.state = "reject"
        self.message_post(body=_("Anticipo rechazado."))
