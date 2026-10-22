# -*- coding: utf-8 -*-
"""Core payroll configuration models (structures, rules, categories, registers)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class HrPayrollStructure(models.Model):
    _name = "hr.payroll.structure"
    _description = "Salary Structure"
    _order = "sequence, type_id, name"

    @api.model
    def _default_parent_structure(self):
        return self.env.ref("l10n_hn_payroll_base.structure_base", raise_if_not_found=False)

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10, index=True)
    code = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    note = fields.Text(string="Description")
    parent_id = fields.Many2one("hr.payroll.structure", string="Parent", default=_default_parent_structure)
    children_ids = fields.One2many("hr.payroll.structure", "parent_id", string="Children", copy=True)
    rule_ids = fields.Many2many(
        "hr.salary.rule",
        "hr_structure_salary_rule_rel",
        "struct_id",
        "rule_id",
        string="Salary Rules",
    )
    active = fields.Boolean(default=True)
    type_id = fields.Many2one(
        "hr.payroll.structure.type",
        string="Structure Type",
        index=True,
    )
    country_id = fields.Many2one(
        "res.country",
        string="Country",
        default=lambda self: self.env.company.country_id,
        domain=lambda self: [("id", "in", self.env.companies.country_id.ids)],
    )
    schedule_pay = fields.Selection(
        selection=lambda self: self.env["hr.payroll.structure.type"]._get_selection_schedule_pay(),
        string="Scheduled pay",
        default="monthly",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Salary journal",
        check_company=True,
        domain="[('type', '=', 'general'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Default accounting journal for payslips using this structure (when the contract has no journal).",
    )
    restricted_contract_type_ids = fields.Many2many(
        "hr.contract.type",
        "hr_payroll_structure_contract_type_rel",
        "structure_id",
        "contract_type_id",
        string="Employment types",
        help="If set, only employees with these contract types are included in pay runs for this structure. "
        "Leave empty for all employment types.",
    )
    ytd_computation = fields.Boolean(
        string="Year-to-date computation",
        default=False,
        help="Enable when salary rules aggregate year-to-date amounts (extensions may use this flag).",
    )
    payslip_report_id = fields.Many2one(
        "ir.actions.report",
        string="Payslip report",
        domain="[('model', '=', 'hr.payslip')]",
        help="PDF report used when printing payslips for this structure (defaults to the standard payslip).",
    )
    payslip_name_pattern = fields.Char(
        string="Payslip name pattern",
        help="Optional. Placeholders: {employee}, {month}, {year} (from period start). Used when generating draft payslip names.",
    )
    hide_basic_on_pdf = fields.Boolean(
        string="Hide basic on PDF",
        default=False,
        help="If set, the BASIC line is omitted from the printed payslip (other rules still print).",
    )
    unpaid_work_entry_type_ids = fields.Many2many(
        "hr.work.entry.type",
        "l10n_hn_structure_unpaid_work_entry_rel",
        "struct_id",
        "work_entry_type_id",
        string="Unpaid Work Entry Types",
    )
    use_worked_day_lines = fields.Boolean(
        default=True,
        help="If set, worked days lines drive absence-related day counts on payslips.",
    )
    worked_days_from_work_entries = fields.Boolean(
        string="Worked days from work entries",
        default=False,
        help="Build payslip worked-day lines from validated hr.work.entry records for "
        "the contract version in the payslip period. Conflicting entries block payroll until resolved. "
        "If no validated entries exist in the period, the calendar-based calculation is used instead.",
    )
    input_line_type_ids = fields.Many2many(
        "hr.payslip.input.type",
        "hr_payroll_structure_hr_payslip_input_type_rel",
        "structure_id",
        "input_type_id",
        string="Other input lines",
        help="Extra payslip inputs (by type) merged with rule-defined inputs when generating draft payslips.",
    )
    assignment_version_ids = fields.One2many(
        "hr.version",
        "struct_id",
        string="Contract versions",
        help="Contract versions (hr.version) linked to this salary structure.",
    )
    salary_rule_count = fields.Integer(
        string="Salary rules",
        compute="_compute_salary_rule_count",
    )
    contract_usage_count = fields.Integer(
        string="Count",
        compute="_compute_contract_usage_count",
        store=True,
    )

    @api.depends("rule_ids")
    def _compute_salary_rule_count(self):
        for struct in self:
            struct.salary_rule_count = len(struct.get_all_rules())

    @api.depends("assignment_version_ids", "assignment_version_ids.active")
    def _compute_contract_usage_count(self):
        for struct in self:
            struct.contract_usage_count = len(struct.assignment_version_ids.filtered("active"))

    def action_open_salary_rules(self):
        self.ensure_one()
        rule_ids = [rid for rid, _seq in self.get_all_rules()]
        return {
            "type": "ir.actions.act_window",
            "name": _("Salary rules"),
            "res_model": "hr.salary.rule",
            "view_mode": "list,form",
            "domain": [("id", "in", rule_ids)],
            "context": {"default_struct_id": self.id},
        }

    def action_open_contract_versions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Contract versions"),
            "res_model": "hr.version",
            "view_mode": "list,form",
            "domain": [("struct_id", "=", self.id)],
            "context": {"default_struct_id": self.id},
        }

    @api.constrains("parent_id")
    def _check_parent_id(self):
        if self._has_cycle("parent_id"):
            raise ValidationError(_("You cannot create a recursive salary structure."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("type_id") and not vals.get("schedule_pay"):
                stype = self.env["hr.payroll.structure.type"].browse(vals["type_id"])
                vals.setdefault("schedule_pay", stype.default_schedule_pay or "monthly")
        return super().create(vals_list)

    @api.onchange("type_id")
    def _onchange_payroll_structure_type_id(self):
        if self.type_id and self.type_id.default_schedule_pay:
            self.schedule_pay = self.type_id.default_schedule_pay

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {}, code=_("%s (copy)") % self.code)
        return super().copy(default)

    def get_all_rules(self):
        """Union of rules on the structure M2M and rules whose struct_id points here."""
        Rule = self.env["hr.salary.rule"]
        all_rules = []
        seen = set()
        for struct in self:
            for rid, seq in struct.rule_ids._recursive_search_of_rules():
                if rid not in seen:
                    seen.add(rid)
                    all_rules.append((rid, seq))
            for rule in Rule.search([("struct_id", "=", struct.id)]):
                if rule.id not in seen:
                    seen.add(rule.id)
                    all_rules.append((rule.id, rule.sequence))
        return all_rules

    def _get_parent_structure(self):
        parent = self.mapped("parent_id")
        if parent:
            parent = parent._get_parent_structure()
        return parent + self


class HrContributionRegister(models.Model):
    _name = "hr.contribution.register"
    _description = "Contribution Register"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    partner_id = fields.Many2one("res.partner", string="Partner")
    name = fields.Char(required=True)
    register_line_ids = fields.One2many(
        "hr.payslip.line",
        "register_id",
        string="Register Lines",
        readonly=True,
    )
    note = fields.Text(string="Description")


class HrSalaryRuleCategory(models.Model):
    _name = "hr.salary.rule.category"
    _description = "Salary Rule Category"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    color = fields.Integer(
        string="Color",
        default=0,
        help="Display color for this category in lists (0 = default: Odoo palette 0–11).",
    )
    parent_id = fields.Many2one(
        "hr.salary.rule.category",
        string="Parent",
        help="Used for hierarchical reporting.",
    )
    children_ids = fields.One2many("hr.salary.rule.category", "parent_id", string="Children")
    note = fields.Text(string="Description")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.constrains("parent_id")
    def _check_parent_id(self):
        if self._has_cycle("parent_id"):
            raise ValidationError(_("You cannot create recursive salary categories."))


class HrSalaryRule(models.Model):
    _name = "hr.salary.rule"
    _description = "Salary Rule"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Referenced by other rules (case sensitive).",
    )
    sequence = fields.Integer(required=True, index=True, default=5)
    quantity = fields.Char(
        default="1.0",
        help="Python expression for quantity (e.g. worked days).",
    )
    category_id = fields.Many2one("hr.salary.rule.category", string="Category", required=True)
    active = fields.Boolean(default=True)
    appears_on_payslip = fields.Boolean(default=True)
    parent_rule_id = fields.Many2one("hr.salary.rule", string="Parent Salary Rule", index=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    condition_select = fields.Selection(
        [
            ("none", "Always True"),
            ("range", "Range"),
            ("python", "Python Expression"),
        ],
        default="none",
        required=True,
    )
    condition_range = fields.Char(default="contract.wage")
    condition_python = fields.Text(
        required=True,
        default="result = True",
    )
    condition_range_min = fields.Float()
    condition_range_max = fields.Float()
    amount_select = fields.Selection(
        [
            ("percentage", "Percentage (%)"),
            ("fix", "Fixed Amount"),
            ("code", "Python Code"),
        ],
        string="Amount Type",
        required=True,
        default="fix",
    )
    amount_fix = fields.Float(string="Fixed Amount", digits="HN Payroll")
    amount_percentage = fields.Float(string="Percentage (%)", digits="HN Payroll Rate")
    amount_python_compute = fields.Text(default="result = contract.wage * 0.1")
    amount_percentage_base = fields.Char()
    child_ids = fields.One2many("hr.salary.rule", "parent_rule_id", string="Child Rules", copy=True)
    register_id = fields.Many2one("hr.contribution.register", string="Contribution Register")
    input_ids = fields.One2many("hr.rule.input", "input_id", string="Inputs", copy=True)
    note = fields.Text()
    struct_id = fields.Many2one("hr.payroll.structure", string="Salary Structure")

    def _raise_error(self, _localdict, message, exc):
        raise UserError(_("%(msg)s %(rule)s: %(err)s") % {"msg": message, "rule": self.display_name, "err": exc})

    def _recursive_search_of_rules(self):
        children_rules = []
        for rule in self.filtered(lambda r: r.child_ids):
            children_rules += rule.child_ids._recursive_search_of_rules()
        return [(rule.id, rule.sequence) for rule in self] + children_rules

    def _compute_rule(self, localdict):
        """Return (amount, quantity, rate_percent)."""
        self.ensure_one()
        localdict["localdict"] = localdict
        if self.amount_select == "fix":
            try:
                return self.amount_fix or 0.0, float(safe_eval(self.quantity, localdict)), 100.0
            except Exception as exc:
                self._raise_error(localdict, _("Invalid quantity expression:"), exc)
        if self.amount_select == "percentage":
            try:
                return (
                    float(safe_eval(self.amount_percentage_base, localdict)),
                    float(safe_eval(self.quantity, localdict)),
                    self.amount_percentage or 0.0,
                )
            except Exception as exc:
                self._raise_error(localdict, _("Invalid percentage base or quantity:"), exc)
        try:
            safe_eval(self.amount_python_compute or "0.0", localdict, mode="exec")
            return (
                float(localdict["result"]),
                localdict.get("result_qty", 1.0),
                localdict.get("result_rate", 100.0),
            )
        except Exception as exc:
            self._raise_error(localdict, _("Invalid python amount code:"), exc)

    def _satisfy_condition(self, localdict):
        self.ensure_one()
        if self.condition_select == "none":
            return True
        if self.condition_select == "range":
            try:
                result = safe_eval(self.condition_range, localdict)
                return self.condition_range_min <= result <= self.condition_range_max
            except Exception as exc:
                raise UserError(
                    _("Wrong range condition for salary rule %(name)s (%(code)s): %(err)s")
                    % {"name": self.name, "code": self.code, "err": exc}
                ) from exc
        try:
            safe_eval(self.condition_python, localdict, mode="exec")
            return bool(localdict.get("result"))
        except Exception as exc:
            raise UserError(
                _("Wrong python condition for salary rule %(name)s (%(code)s): %(err)s")
                % {"name": self.name, "code": self.code, "err": exc}
            ) from exc

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        structs = rules.struct_id
        if structs:
            structs.invalidate_recordset(["salary_rule_count"])
        return rules

    def write(self, vals):
        old_structs = self.struct_id
        res = super().write(vals)
        touched = old_structs | self.struct_id
        if touched:
            touched.invalidate_recordset(["salary_rule_count"])
        return res

    def unlink(self):
        structs = self.struct_id
        res = super().unlink()
        if structs:
            structs.invalidate_recordset(["salary_rule_count"])
        return res


class HrRuleInput(models.Model):
    _name = "hr.rule.input"
    _description = "Salary Rule Input"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    input_id = fields.Many2one("hr.salary.rule", string="Salary Rule", required=True, ondelete="cascade")


class HrVersionAdvantageTemplate(models.Model):
    """Optional contract numeric templates (legacy compatibility)."""

    _name = "hr.version.advantage.template"
    _description = "Contract Advantage Template"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    lower_bound = fields.Float()
    upper_bound = fields.Float()
    default_value = fields.Float()
