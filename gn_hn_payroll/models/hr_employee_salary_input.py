from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployeeSalaryInput(models.Model):
    _name = "hr.employee.salary.input"
    _description = "Employee Salary Input"
    _order = "sequence, id"

    name = fields.Char(string="Descripcion")
    sequence = fields.Integer(default=10)
    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="employee_id.company_id",
        store=True,
        readonly=True,
    )
    input_type_id = fields.Many2one(
        "hr.payslip.input.type",
        string="Concepto",
        required=True,
        domain="[('id', 'in', allowed_input_type_ids)]",
    )
    periodicity = fields.Selection(
        [
            ("finite", "Finita"),
            ("infinite", "Infinita"),
        ],
        string="Periocidad",
        required=True,
        default="finite",
        help="Indica si el beneficio o deducción tiene un número limitado de pagos.",
    )
    amount = fields.Float(
        digits="Payroll Rate",
        string="Monto",
    )
    quota_amount = fields.Float(
        digits="Payroll Rate",
        string="Cuota",
        required=True,
        help="Monto por cuota para este beneficio o deducción.",
    )
    payments_total = fields.Integer(
        string="# pagos",
        required=True,
        help="Número total de pagos previstos para esta línea.",
    )
    payments_remaining = fields.Integer(
        string="Pagos restantes",
        required=True,
        help="Pagos pendientes por aplicar.",
    )
    ihss_amount = fields.Float(
        digits="Payroll Rate",
        string="Monto IHSS",
        help="Monto mensual a deducir por concepto de IHSS.",
    )
    ihss_deduction_period = fields.Selection(
        [
            ("first_half", "Día 15"),
            ("second_half", "Fin de mes"),
            ("both", "En ambos"),
        ],
        string="Incluir en IHSS",
        default="both",
        help="Determina en qué fecha del mes se aplicará la deducción de IHSS.",
    )
    afp_amount = fields.Float(
        digits="Payroll Rate",
        string="Monto AFP",
        help="Monto mensual a deducir por concepto de AFP.",
    )
    afp_deduction_period = fields.Selection(
        [
            ("first_half", "Día 15"),
            ("second_half", "Fin de mes"),
            ("both", "En ambos"),
        ],
        string="Incluir en AFP",
        default="both",
        help="Determina en qué fecha del mes se aplicará la deducción de AFP.",
    )
    deduction_period = fields.Selection(
        [
            ("first_half", "Día 15"),
            ("second_half", "Fin de mes"),
            ("both", "En ambos"),
        ],
        compute="_compute_deduction_period",
        inverse="_inverse_deduction_period",
        required=True,
        string="Incluir en",
    )
    date_start = fields.Date(string="Desde")
    date_end = fields.Date(string="Hasta")
    struct_ids = fields.Many2many(
        "hr.payroll.structure",
        string="Estructuras",
        help="Limita este Salary Input a una o varias estructuras especificas.",
    )
    allowed_input_type_ids = fields.Many2many(
        "hr.payslip.input.type",
        compute="_compute_allowed_input_type_ids",
        string="Tipos permitidos",
    )
    input_type_code = fields.Char(
        related="input_type_id.code",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)

    @api.depends("employee_id", "employee_id.structure_id")
    def _compute_allowed_input_type_ids(self):
        InputType = self.env["hr.payslip.input.type"]
        all_types = InputType.search([])
        for record in self:
            structure = record.employee_id.structure_id
            if structure:
                record.allowed_input_type_ids = structure.input_line_type_ids
            else:
                record.allowed_input_type_ids = all_types

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for record in self:
            if (
                record.date_start
                and record.date_end
                and record.date_end < record.date_start
            ):
                raise ValidationError(
                    _("La fecha final no puede ser anterior a la fecha de inicio.")
                )

    @api.constrains("quota_amount")
    def _check_positive_quota(self):
        for record in self:
            if record.quota_amount is not None and record.quota_amount <= 0.0:
                raise ValidationError(_("El monto de la cuota debe ser mayor que cero."))

    @api.constrains("amount")
    def _check_positive_amount(self):
        for record in self:
            if record.input_type_code in ("IHSS", "AFP"):
                continue
            if record.amount is None or record.amount <= 0.0:
                raise ValidationError(_("El monto total debe ser mayor que cero."))

    @api.onchange("input_type_id")
    def _onchange_input_type_id(self):
        self._reset_ihss_fields()
        self._reset_afp_fields()
        if not self.input_type_id:
            return
        if self._is_ihss_input():
            self._apply_ihss_defaults()
        elif self._is_afp_input():
            self._apply_afp_defaults()
        self._sync_amount_from_quota()

    @api.onchange("quota_amount", "payments_total")
    def _onchange_quota_or_payments(self):
        self._apply_payments_default()
        self._sync_amount_from_quota()

    @api.onchange("deduction_period")
    def _onchange_deduction_period(self):
        self._sync_amount_from_quota()

    def _is_ihss_input(self):
        self.ensure_one()
        return self.input_type_code == "IHSS"

    def _is_afp_input(self):
        self.ensure_one()
        return self.input_type_code == "AFP"

    def _reset_ihss_fields(self):
        self.ihss_amount = 0.0
        self.ihss_deduction_period = "both"

    def _reset_afp_fields(self):
        self.afp_amount = 0.0
        self.afp_deduction_period = "both"

    @api.depends("input_type_code", "ihss_deduction_period", "afp_deduction_period")
    def _compute_deduction_period(self):
        for record in self:
            period_code = False
            if record.input_type_code == "IHSS":
                period_code = record.ihss_deduction_period
            elif record.input_type_code == "AFP":
                period_code = record.afp_deduction_period
            record.deduction_period = period_code

    def _inverse_deduction_period(self):
        for record in self:
            period_code = record.deduction_period
            if record.input_type_code == "IHSS":
                record.ihss_deduction_period = period_code or "both"
            elif record.input_type_code == "AFP":
                record.afp_deduction_period = period_code or "both"

    def _apply_ihss_defaults(self):
        settings = (
            self.env["hr.ihss.settings"]
            .search([("state", "=", "validated")], order="create_date desc", limit=1)
        )
        if not settings:
            return
        include_in = settings.include_in
        self.ihss_amount = settings.ihss_fee
        period_map = {
            "first": "first_half",
            "second": "second_half",
            "both": "both",
        }
        self.ihss_deduction_period = period_map.get(include_in, "both")
        if self.ihss_deduction_period == "both":
            self.amount = settings.bi_weekly_fee or (settings.ihss_fee / 2.0)
        else:
            self.amount = settings.ihss_fee

    def _apply_afp_defaults(self):
        employee = self.employee_id
        domain = [("state", "=", "validated")]
        if employee and employee.company_id:
            domain.append(("company_id", "=", employee.company_id.id))
        settings = (
            self.env["hr.afp.settings"]
            .search(domain, order="create_date desc", limit=1)
        )
        if not settings:
            return
        line = settings.line_ids.filtered(lambda l: l.employee_id == employee)[:1]
        if not line:
            return
        self.afp_amount = line.afp_amount
        period_map = {
            "first": "first_half",
            "second": "second_half",
            "both": "both",
        }
        self.afp_deduction_period = period_map.get(settings.include_in, "both")
        if self.afp_deduction_period == "both":
            per_period_amount = line.quincena_amount or (line.afp_amount / 2.0 if line.afp_amount else 0.0)
        else:
            per_period_amount = line.afp_amount
        if per_period_amount is not None:
            self.amount = per_period_amount
        self._apply_payments_default()
        self._sync_amount_from_quota()

    def _sync_amount_from_quota(self):
        for record in self:
            if record.input_type_code in ("IHSS", "AFP"):
                continue
            quota = record.quota_amount or 0.0
            total = record.payments_total or 0.0
            computed_amount = quota * total
            if record.deduction_period == "both":
                computed_amount = computed_amount * 2.0
            if not record.id:
                record.amount = computed_amount
                continue
            record.with_context(skip_amount_sync=True).amount = computed_amount

    def _apply_payments_default(self):
        for record in self:
            if record.periodicity == "finite":
                if record.payments_total and (record.payments_remaining in (False, None, 0)):
                    record.payments_remaining = record.payments_total

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("skip_amount_sync"):
            records._apply_payments_default()
            records._sync_amount_from_quota()
        return records

    def write(self, vals):
        if self.env.context.get("skip_amount_sync"):
            return super().write(vals)
        res = super().write(vals)
        self.with_context(skip_amount_sync=True)._apply_payments_default()
        self.with_context(skip_amount_sync=True)._sync_amount_from_quota()
        return res

    def _get_amount_for_payslip(self, payslip):
        self.ensure_one()
        base_amount = self.amount
        if not payslip or not payslip.date_from or not payslip.date_to:
            return True, self._round_amount(base_amount, payslip)
        if self._is_ihss_input():
            return self._compute_scheduled_amount(
                self.ihss_amount or self.amount,
                self.ihss_deduction_period or "both",
                payslip,
            )
        if self._is_afp_input():
            return self._compute_scheduled_amount(
                self.afp_amount or self.amount,
                self.afp_deduction_period or "both",
                payslip,
            )
        return self._compute_general_payslip_amount(payslip)

    def _compute_general_payslip_amount(self, payslip):
        self.ensure_one()
        per_period_amount = self.quota_amount or 0.0
        if not per_period_amount:
            return False, 0.0
        schedule = self.deduction_period or "first_half"
        if not payslip or not payslip.date_from or not payslip.date_to:
            return True, self._round_amount(per_period_amount, payslip)
        period_bucket = payslip._get_ihss_period_bucket()
        if schedule == "both":
            if period_bucket in ("first_half", "second_half"):
                return True, self._round_amount(per_period_amount, payslip)
            return False, 0.0
        if period_bucket == schedule:
            return True, self._round_amount(per_period_amount, payslip)
        return False, 0.0

    def _round_amount(self, amount, payslip):
        currency = getattr(payslip.company_id, "currency_id", False) or self.env.company.currency_id
        if currency:
            return currency.round(amount)
        return amount

    def _compute_scheduled_amount(self, total_amount, schedule, payslip):
        if not total_amount:
            return False, 0.0
        payslip_period = payslip._get_ihss_period_bucket()
        if payslip_period == "first_half":
            if schedule == "first_half":
                return True, self._round_amount(total_amount, payslip)
            if schedule == "both":
                return True, self._round_amount(total_amount / 2.0, payslip)
            return False, 0.0
        if payslip_period == "second_half":
            if schedule == "second_half":
                return True, self._round_amount(total_amount, payslip)
            if schedule == "both":
                return True, self._round_amount(total_amount / 2.0, payslip)
            return False, 0.0
        return True, self._round_amount(total_amount, payslip)
