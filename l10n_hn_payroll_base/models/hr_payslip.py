# -*- coding: utf-8 -*-
"""Payslip engine: computation, batches, worked days and salary lines."""

import babel.dates
from collections import defaultdict
from datetime import date, datetime, time

from dateutil.relativedelta import relativedelta
from pytz import timezone

from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, format_date
from odoo.tools.safe_eval import safe_eval


class HrPayslip(models.Model):
    _name = "hr.payslip"
    _description = "Pay Slip"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_to desc, id desc"

    _PAYSLIP_DONE_STATES = frozenset({"done", "paid"})

    struct_id = fields.Many2one(
        "hr.payroll.structure",
        string="Structure",
        help="Salary rules applied to this payslip.",
    )
    name = fields.Char(string="Payslip Name", tracking=True)
    number = fields.Char(string="Reference", copy=False, tracking=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True, index=True, tracking=True)
    date_from = fields.Date(required=True, default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_to = fields.Date(
        required=True,
        default=lambda self: fields.Date.to_string(
            (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
        ),
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("verify", "Waiting"),
            ("done", "Validated"),
            ("paid", "Paid"),
            ("cancel", "Rejected"),
        ],
        string="Status",
        default="draft",
        copy=False,
        tracking=True,
    )
    line_ids = fields.One2many(
        "hr.payslip.line",
        "slip_id",
        string="Payslip Lines",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
        default=lambda self: self.env.company,
    )
    worked_days_line_ids = fields.One2many(
        "hr.payslip.worked_days",
        "payslip_id",
        string="Worked Days",
        copy=True,
        readonly=True,
    )
    input_line_ids = fields.One2many(
        "hr.payslip.input",
        "payslip_id",
        string="Inputs",
        copy=True,
        readonly=True,
    )
    paid = fields.Boolean(string="Payment Order", readonly=True, copy=False)
    note = fields.Text(string="Internal Note")
    contract_id = fields.Many2one("hr.version", string="Contract", tracking=True)
    details_by_salary_rule_category = fields.One2many(
        "hr.payslip.line",
        compute="_compute_details_by_salary_rule_category",
        string="Lines by Category",
    )
    credit_note = fields.Boolean(string="Credit Note", help="Refund of another payslip.")
    payslip_run_id = fields.Many2one("hr.payslip.run", string="Pay run", readonly=True, copy=False)
    is_off_cycle = fields.Boolean(
        string="Off-cycle",
        default=False,
        help="Indicates a payslip outside the regular payroll calendar (bonus, adjustment, etc.).",
    )
    total_worked_days = fields.Float(
        string="Worked days",
        compute="_compute_payslip_wage_breakdown",
        digits=(16, 2),
    )
    total_worked_hours = fields.Float(
        string="Worked hours",
        compute="_compute_total_worked_hours",
        digits=(16, 2),
    )
    payslip_warn_period_mismatch = fields.Boolean(
        string="Period/structure mismatch warning",
        compute="_compute_payslip_dashboard_warnings",
    )
    payslip_warn_no_bank = fields.Boolean(
        string="Missing bank account warning",
        compute="_compute_payslip_dashboard_warnings",
    )
    basic_wage = fields.Monetary(
        string="Basic wage",
        compute="_compute_payslip_wage_breakdown",
        currency_field="currency_id",
    )
    gross_wage = fields.Monetary(
        string="Gross wage",
        compute="_compute_payslip_wage_breakdown",
        currency_field="currency_id",
    )
    payslip_line_stats = fields.Integer(compute="_compute_payslip_line_stats", string="Lines")
    payslip_net_total = fields.Monetary(
        compute="_compute_payslip_net_total",
        currency_field="currency_id",
        string="Net (computed)",
    )
    currency_id = fields.Many2one(related="company_id.currency_id")

    def _compute_details_by_salary_rule_category(self):
        for payslip in self:
            payslip.details_by_salary_rule_category = payslip.line_ids.filtered(lambda l: l.category_id)

    def _compute_payslip_line_stats(self):
        for rec in self:
            rec.payslip_line_stats = len(rec.line_ids)

    def _compute_payslip_net_total(self):
        for rec in self:
            net_lines = rec.line_ids.filtered(lambda l: l.category_id.code == "NET")
            rec.payslip_net_total = sum(net_lines.mapped("total"))

    @api.depends("worked_days_line_ids.number_of_days", "line_ids.total", "line_ids.category_id.code")
    def _compute_payslip_wage_breakdown(self):
        for rec in self:
            rec.total_worked_days = sum(rec.worked_days_line_ids.mapped("number_of_days"))
            basic = gross = 0.0
            for line in rec.line_ids:
                cat_code = line.category_id.code if line.category_id else ""
                if cat_code == "BASIC":
                    basic += line.total or 0.0
                elif cat_code == "GROSS":
                    gross += line.total or 0.0
            rec.basic_wage = basic
            rec.gross_wage = gross

    @api.depends("worked_days_line_ids.number_of_hours")
    def _compute_total_worked_hours(self):
        for rec in self:
            rec.total_worked_hours = sum(rec.worked_days_line_ids.mapped("number_of_hours"))

    @api.depends(
        "contract_id.struct_id",
        "date_from",
        "date_to",
        "struct_id",
        "payslip_run_id.structure_id",
        "payslip_run_id.date_start",
        "payslip_run_id.date_end",
        "employee_id.bank_account_ids",
    )
    def _compute_payslip_dashboard_warnings(self):
        for rec in self:
            warn_period = False
            emp = rec.employee_id
            rec.payslip_warn_no_bank = bool(emp and not emp.bank_account_ids)
            run = rec.payslip_run_id
            if run:
                if run.structure_id and rec.struct_id and rec.struct_id != run.structure_id:
                    warn_period = True
                elif (
                    rec.date_from
                    and rec.date_to
                    and run.date_start
                    and run.date_end
                    and (rec.date_from != run.date_start or rec.date_to != run.date_end)
                ):
                    warn_period = True
            c = rec.contract_id
            if c and rec.struct_id and c.struct_id and rec.struct_id != c.struct_id:
                warn_period = True
            rec.payslip_warn_period_mismatch = warn_period

    def payslip_line_count(self):
        self.ensure_one()
        return {
            "name": _("Payslip Lines"),
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "res_model": "hr.payslip.line",
            "domain": [("slip_id", "=", self.id)],
            "context": {"default_slip_id": self.id},
        }

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        if any(p.date_from > p.date_to for p in self):
            raise ValidationError(_("Period start must be before end."))

    def copy(self, default=None):
        default = dict(default or {})
        copied = super().copy(default)
        for line in self.input_line_ids:
            line.copy({"payslip_id": copied.id})
        return copied

    def action_payslip_draft(self):
        return self.write({"state": "draft"})

    def action_payslip_done(self):
        if not self.env.context.get("without_compute_sheet"):
            self.compute_sheet()
        return self.write({"state": "done", "paid": False})

    def action_payslip_mark_paid(self):
        invalid = self.filtered(lambda s: s.state != "done")
        if invalid:
            raise UserError(_("Only validated payslips can be marked as paid."))
        return self.write({"state": "paid", "paid": True})

    def action_payslip_cancel(self):
        if any(s.state in self._PAYSLIP_DONE_STATES for s in self):
            raise UserError(_("You cannot cancel a validated payslip."))
        return self.write({"state": "cancel"})

    def action_print_payslip(self):
        """Same entry point name as Enterprise hr_payroll (GN / email extensions)."""
        self.ensure_one()
        report = self.struct_id.payslip_report_id if self.struct_id else False
        if not report:
            report = self.env.ref("l10n_hn_payroll_base.action_report_payslip", raise_if_not_found=False)
        if not report:
            raise UserError(_("No payslip report is configured."))
        return report.report_action(self)

    def _apply_structure_payslip_name_pattern(self):
        """Apply hr.payroll.structure payslip_name_pattern if set."""
        for rec in self:
            struct = rec.struct_id
            if not struct or not struct.payslip_name_pattern:
                continue
            df = rec.date_from
            values = {
                "employee": rec.employee_id.name or "",
                "month": str(df.month) if df else "",
                "year": str(df.year) if df else "",
            }
            try:
                rec.name = struct.payslip_name_pattern.format(**values)
            except (KeyError, ValueError):
                name = struct.payslip_name_pattern
                for key, val in values.items():
                    name = name.replace("{%s}" % key, val)
                rec.name = name

    def refund_sheet(self):
        new_slips = self.env["hr.payslip"]
        for payslip in self:
            if payslip.state != "done":
                raise UserError(_("Only validated payslips that are not yet paid can be refunded."))
            copy_vals = {"credit_note": True, "name": _("Refund: %s") % payslip.name}
            copied = payslip.copy(copy_vals)
            number = copied.number or self.env["ir.sequence"].next_by_code("salary.slip")
            copied.write({"number": number})
            copied.with_context(without_compute_sheet=True).action_payslip_done()
            new_slips |= copied
        return {
            "type": "ir.actions.act_window",
            "name": _("Refund payslips"),
            "res_model": "hr.payslip",
            "view_mode": "list,form",
            "domain": [("id", "in", new_slips.ids)],
        }

    def unlink(self):
        if any(s.state not in ("draft", "cancel") for s in self):
            raise UserError(_("Only draft or cancelled payslips can be deleted."))
        return super().unlink()

    @api.model
    def get_contract(self, employee, date_from, date_to):
        clause_1 = ["&", ("date_end", "<=", date_to), ("date_end", ">=", date_from)]
        clause_2 = ["&", ("date_start", "<=", date_to), ("date_start", ">=", date_from)]
        clause_3 = ["&", ("date_start", "<=", date_from), "|", ("date_end", "=", False), ("date_end", ">=", date_to)]
        domain = (
            [("employee_id", "=", employee.id), ("active", "=", True), "|", "|"]
            + clause_1
            + clause_2
            + clause_3
        )
        return self.env["hr.version"].search(domain).ids

    def compute_sheet(self):
        for payslip in self:
            number = payslip.number or self.env["ir.sequence"].next_by_code("salary.slip")
            payslip.line_ids.unlink()
            contract_ids = payslip.contract_id.ids or payslip.get_contract(
                payslip.employee_id, payslip.date_from, payslip.date_to
            )
            lines = [(0, 0, line) for line in payslip._get_payslip_lines(contract_ids, payslip.id)]
            payslip.write({"line_ids": lines, "number": number})
        return True

    @api.model
    def _hn_payroll_worked_days_from_work_entries(self, contract, date_from, date_to):
        """Aggregate validated hr.work.entry into payslip worked-day lines (CE clean-room).

        Returns a list of value dicts, or None to signal fallback to calendar-based lines.
        """
        WorkEntry = self.env["hr.work.entry"]
        if WorkEntry.search_count(
            [
                ("version_id", "=", contract.id),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
                ("active", "=", True),
                ("state", "=", "conflict"),
            ],
            limit=1,
        ):
            raise UserError(
                _(
                    "There are conflicting work entries for %(employee)s in this period. "
                    "Fix them before computing worked days on the payslip.",
                    employee=contract.employee_id.display_name,
                )
            )
        entries = WorkEntry.search(
            [
                ("version_id", "=", contract.id),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
                ("active", "=", True),
                ("state", "=", "validated"),
            ]
        )
        if not entries:
            return None

        calendar = contract.resource_calendar_id
        hours_per_day = (calendar.hours_per_day if calendar else 0.0) or 8.0

        buckets = defaultdict(lambda: {"hours": 0.0, "type": None})
        for entry in entries:
            wt = entry.work_entry_type_id
            code = (wt.code or "").strip() or f"WE{wt.id}"
            b = buckets[code]
            b["hours"] += entry.duration or 0.0
            if b["type"] is None:
                b["type"] = wt

        lines = []
        for code, data in buckets.items():
            wt = data["type"]
            hours = data["hours"]
            days = float_round(hours / hours_per_day, 2) if hours_per_day else 0.0
            lines.append(
                {
                    "name": wt.name or code,
                    "sequence": wt.sequence if wt else 25,
                    "code": code,
                    "number_of_days": days,
                    "number_of_hours": float_round(hours, 2),
                    "contract_id": contract.id,
                    "work_entry_type_id": wt.id if wt else False,
                }
            )
        # Non-leave lines first, then by type sequence and code (stable, rule-friendly order).
        lines.sort(key=lambda row: (buckets[row["code"]]["type"].is_leave, row["sequence"], row["code"]))
        return lines

    @api.model
    def get_worked_day_lines_struct(self, contracts, date_from, date_to):
        res = []
        d_from = fields.Date.to_date(date_from)
        d_to = fields.Date.to_date(date_to)
        for contract in contracts.filtered("resource_calendar_id"):
            struct = contract.struct_id
            if (
                struct
                and struct.worked_days_from_work_entries
                and "hr.work.entry" in self.env
            ):
                entry_lines = self._hn_payroll_worked_days_from_work_entries(contract, d_from, d_to)
                if entry_lines is not None:
                    res.extend(entry_lines)
                    continue
            day_from = datetime.combine(d_from, time.min)
            day_to = datetime.combine(d_to, time.max)
            calendar = contract.resource_calendar_id
            tzname = calendar.tz or self.env.context.get("tz") or "UTC"
            tz = timezone(tzname)
            leaves = {}
            for day, hours, leave in contract.employee_id.list_leaves(day_from, day_to, calendar=calendar):
                holiday = leave[:1].holiday_id
                current = leaves.setdefault(
                    holiday.holiday_status_id,
                    {
                        "name": holiday.holiday_status_id.name or _("Global Leaves"),
                        "sequence": 5,
                        "code": holiday.holiday_status_id.name or "GLOBAL",
                        "number_of_days": 0.0,
                        "number_of_hours": 0.0,
                        "contract_id": contract.id,
                        "work_entry_type_id": (
                            holiday.holiday_status_id.work_entry_type_id.id
                            if getattr(holiday.holiday_status_id, "work_entry_type_id", False)
                            else False
                        ),
                    },
                )
                current["number_of_hours"] += hours
                work_hours = calendar.get_work_hours_count(
                    tz.localize(datetime.combine(day, time.min)),
                    tz.localize(datetime.combine(day, time.max)),
                    compute_leaves=False,
                )
                if work_hours:
                    current["number_of_days"] += hours / work_hours
            work_data = contract.employee_id._get_work_days_data_batch(
                day_from, day_to, calendar=calendar
            )
            emp_id = contract.employee_id.id
            attendances = {
                "name": _("Normal Working Days paid at 100%"),
                "sequence": 1,
                "code": "WORK100",
                "number_of_days": work_data[emp_id]["days"],
                "number_of_hours": work_data[emp_id]["hours"],
                "contract_id": contract.id,
            }
            res.append(attendances)
            res.extend(leaves.values())
        return res

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        del date_from, date_to  # kept for API compatibility
        res = []
        structure_ids = contracts.get_all_structures()
        structures = self.env["hr.payroll.structure"].browse(structure_ids)
        rule_ids = structures.get_all_rules()
        sorted_rule_ids = [rid for rid, seq in sorted(rule_ids, key=lambda x: x[1])]
        inputs = self.env["hr.salary.rule"].browse(sorted_rule_ids).mapped("input_ids")
        input_types = self.env["hr.payslip.input.type"]
        for struct in structures:
            if struct.input_line_type_ids:
                input_types |= struct.input_line_type_ids
        for contract in contracts:
            seen_codes = set()
            for pay_input in inputs:
                if pay_input.code in seen_codes:
                    continue
                seen_codes.add(pay_input.code)
                res.append(
                    {
                        "name": pay_input.name,
                        "code": pay_input.code,
                        "contract_id": contract.id,
                    }
                )
            for it in input_types:
                if it.code in seen_codes:
                    continue
                seen_codes.add(it.code)
                res.append(
                    {
                        "name": it.name,
                        "code": it.code,
                        "contract_id": contract.id,
                        "input_type_id": it.id,
                    }
                )
        return self._apply_version_input_templates(contracts, res)

    @api.model
    def _payslip_input_type_allowed_for_contract(self, contract, input_type):
        """True if input_type may appear on payslips for this contract version."""
        if not input_type:
            return False
        sids = contract.get_all_structures()
        if not sids:
            return False
        structs = self.env["hr.payroll.structure"].browse(sids)
        if any(not s.input_line_type_ids for s in structs):
            return True
        allowed_ids = set(structs.input_line_type_ids.ids)
        return input_type.id in allowed_ids

    @api.model
    def _apply_version_input_templates(self, contracts, res):
        """Merge hr.version default input amounts; add lines allowed on structure."""
        index_by_contract_code = {}
        for i, row in enumerate(res):
            cid, code = row.get("contract_id"), row.get("code")
            if cid and code:
                index_by_contract_code[(cid, code)] = i
        for contract in contracts:
            for tpl in contract.payslip_input_template_line_ids.sorted("sequence"):
                it = tpl.input_type_id
                if not it or not it.active:
                    continue
                code = it.code
                key = (contract.id, code)
                if key in index_by_contract_code:
                    row = res[index_by_contract_code[key]]
                    row["amount"] = tpl.default_amount
                    row.setdefault("input_type_id", it.id)
                elif self._payslip_input_type_allowed_for_contract(contract, it):
                    res.append(
                        {
                            "name": it.name,
                            "code": code,
                            "contract_id": contract.id,
                            "input_type_id": it.id,
                            "amount": tpl.default_amount,
                        }
                    )
                    index_by_contract_code[key] = len(res) - 1
        return res

    @api.model
    def _get_payslip_lines(self, contract_ids, payslip_id):
        def _sum_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_category(localdict, category.parent_id, amount)
            if category.code in localdict["categories"].dict:
                localdict["categories"].dict[category.code] += amount
            else:
                localdict["categories"].dict[category.code] = amount
            return localdict

        class _Browsable:
            def __init__(self, employee_id, data, env):
                self.employee_id = employee_id
                self.dict = data if isinstance(data, dict) else {}
                self.env = env

            def __getattr__(self, attr):
                return self.dict.get(attr, 0.0)

        class InputLine(_Browsable):
            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                # SQL-JUSTIFIED: single aggregated read for salary rule inputs (parametrized).
                self.env.cr.execute(
                    """
                    SELECT COALESCE(SUM(pi.amount), 0.0)
                    FROM hr_payslip hp
                    JOIN hr_payslip_input pi ON hp.id = pi.payslip_id
                    WHERE hp.employee_id = %s AND hp.state IN ('done', 'paid')
                      AND hp.date_from >= %s AND hp.date_to <= %s AND pi.code = %s
                    """,
                    (self.employee_id, from_date, to_date, code),
                )
                row = self.env.cr.fetchone()
                return row[0] if row else 0.0

        class WorkedDays(_Browsable):
            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                # SQL-JUSTIFIED: single aggregated read for worked days (parametrized).
                self.env.cr.execute(
                    """
                    SELECT COALESCE(SUM(pi.number_of_days), 0.0), COALESCE(SUM(pi.number_of_hours), 0.0)
                    FROM hr_payslip hp
                    JOIN hr_payslip_worked_days pi ON hp.id = pi.payslip_id
                    WHERE hp.employee_id = %s AND hp.state IN ('done', 'paid')
                      AND hp.date_from >= %s AND hp.date_to <= %s AND pi.code = %s
                    """,
                    (self.employee_id, from_date, to_date, code),
                )
                return self.env.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                row = self._sum(code, from_date, to_date)
                return row[0] if row else 0.0

            def sum_hours(self, code, from_date, to_date=None):
                row = self._sum(code, from_date, to_date)
                return row[1] if row else 0.0

        class Payslips(_Browsable):
            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                # SQL-JUSTIFIED: single aggregated read for payslip line totals (parametrized).
                self.env.cr.execute(
                    """
                    SELECT COALESCE(SUM(CASE WHEN hp.credit_note = FALSE THEN pl.total ELSE -pl.total END), 0.0)
                    FROM hr_payslip hp
                    JOIN hr_payslip_line pl ON hp.id = pl.slip_id
                      WHERE hp.employee_id = %s AND hp.state IN ('done', 'paid')
                      AND hp.date_from >= %s AND hp.date_to <= %s AND pl.code = %s
                    """,
                    (self.employee_id, from_date, to_date, code),
                )
                row = self.env.cr.fetchone()
                return row[0] if row else 0.0

        payslip = self.env["hr.payslip"].browse(payslip_id)
        worked_days_dict = {line.code: line for line in payslip.worked_days_line_ids}
        inputs_dict = {line.code: line for line in payslip.input_line_ids}
        categories = _Browsable(payslip.employee_id.id, {}, self.env)
        baselocaldict = {
            "categories": categories,
            "rules": _Browsable(payslip.employee_id.id, {}, self.env),
            "payslip": Payslips(payslip.employee_id.id, {}, self.env),
            "worked_days": WorkedDays(payslip.employee_id.id, worked_days_dict, self.env),
            "inputs": InputLine(payslip.employee_id.id, inputs_dict, self.env),
        }
        blacklist = []
        result_dict = {}
        contracts = self.env["hr.version"].browse(contract_ids)
        if len(contracts) == 1 and payslip.struct_id:
            structure_ids = list(set(payslip.struct_id._get_parent_structure().ids))
        else:
            structure_ids = contracts.get_all_structures()
        rule_tuples = self.env["hr.payroll.structure"].browse(structure_ids).get_all_rules()
        sorted_rule_ids = [rid for rid, seq in sorted(rule_tuples, key=lambda x: x[1])]
        sorted_rules = self.env["hr.salary.rule"].browse(sorted_rule_ids)

        for contract in contracts:
            employee = contract.employee_id
            localdict = dict(baselocaldict, employee=employee, contract=contract)
            for rule in sorted_rules:
                key = f"{rule.code}-{contract.id}"
                localdict["result"] = None
                localdict["result_qty"] = 1.0
                localdict["result_rate"] = 100.0
                if rule._satisfy_condition(localdict) and rule.id not in blacklist:
                    amount, qty, rate = rule._compute_rule(localdict)
                    previous = localdict.get(rule.code, 0.0)
                    tot_rule = amount * qty * rate / 100.0
                    localdict[rule.code] = tot_rule
                    baselocaldict["rules"].dict[rule.code] = tot_rule
                    localdict = _sum_category(localdict, rule.category_id, tot_rule - previous)
                    result_dict[key] = {
                        "salary_rule_id": rule.id,
                        "contract_id": contract.id,
                        "name": rule.name,
                        "code": rule.code,
                        "category_id": rule.category_id.id,
                        "sequence": rule.sequence,
                        "appears_on_payslip": rule.appears_on_payslip,
                        "condition_select": rule.condition_select,
                        "condition_python": rule.condition_python,
                        "condition_range": rule.condition_range,
                        "condition_range_min": rule.condition_range_min,
                        "condition_range_max": rule.condition_range_max,
                        "amount_select": rule.amount_select,
                        "amount_fix": rule.amount_fix,
                        "amount_python_compute": rule.amount_python_compute,
                        "amount_percentage": rule.amount_percentage,
                        "amount_percentage_base": rule.amount_percentage_base,
                        "register_id": rule.register_id.id,
                        "amount": amount,
                        "employee_id": contract.employee_id.id,
                        "quantity": qty,
                        "rate": rate,
                    }
                else:
                    blacklist.extend(rid for rid, seq in rule._recursive_search_of_rules())
        return list(result_dict.values())

    @api.model
    def onchange_employee_id(self, date_from, date_to, employee_id=False, contract_id=False):
        res = {
            "value": {
                "line_ids": [],
                "input_line_ids": [(2, x) for x in self.input_line_ids.ids],
                "worked_days_line_ids": [(2, x) for x in self.worked_days_line_ids.ids],
                "name": "",
                "contract_id": False,
                "struct_id": False,
            }
        }
        if not employee_id or not date_from or not date_to:
            return res
        employee = self.env["hr.employee"].browse(employee_id)
        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        locale = self.env.context.get("lang") or "en_US"
        res["value"].update(
            {
                "name": _("Salary slip of %(employee)s for %(period)s")
                % {
                    "employee": employee.name,
                    "period": babel.dates.format_date(date=ttyme, format="MMMM-y", locale=locale),
                },
                "company_id": employee.company_id.id,
            }
        )
        if not self.env.context.get("contract"):
            contract_ids = self.get_contract(employee, date_from, date_to)
        elif contract_id:
            contract_ids = [contract_id]
        else:
            contract_ids = self.get_contract(employee, date_from, date_to)
        if not contract_ids:
            return res
        contract = self.env["hr.version"].browse(contract_ids[0])
        res["value"]["contract_id"] = contract.id
        if not contract.struct_id:
            return res
        res["value"]["struct_id"] = contract.struct_id.id
        contracts = self.env["hr.version"].browse(contract_ids)
        res["value"]["worked_days_line_ids"] = self.get_worked_day_lines_struct(contracts, date_from, date_to)
        res["value"]["input_line_ids"] = self.get_inputs(contracts, date_from, date_to)
        return res

    @api.onchange("employee_id", "date_from", "date_to")
    def onchange_employee(self):
        if not (self.employee_id and self.date_from and self.date_to):
            return
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        locale = self.env.context.get("lang") or "en_US"
        self.name = _("Salary slip of %(employee)s for %(period)s") % {
            "employee": employee.name,
            "period": babel.dates.format_date(date=ttyme, format="MMMM-y", locale=locale),
        }
        self.company_id = employee.company_id
        contract_ids = []
        if self.env.context.get("contract") and self.contract_id:
            contract_ids = self.contract_id.ids
        if not contract_ids:
            contract_ids = self.get_contract(employee, date_from, date_to)
            if contract_ids:
                self.contract_id = self.env["hr.version"].browse(contract_ids[0])
        if not self.contract_id.struct_id:
            return
        self.struct_id = self.contract_id.struct_id
        contracts = (
            self.env["hr.version"].browse(contract_ids)
            if contract_ids
            else self.contract_id
        )
        wd = self.get_worked_day_lines_struct(contracts, date_from, date_to)
        self.worked_days_line_ids = [fields.Command.clear()] + [fields.Command.create(vals) for vals in wd]
        inputs = self.get_inputs(contracts, date_from, date_to)
        self.input_line_ids = [fields.Command.clear()] + [fields.Command.create(vals) for vals in inputs]
        self._apply_structure_payslip_name_pattern()

    @api.onchange("contract_id")
    def onchange_contract(self):
        if not self.contract_id:
            self.struct_id = False
            return
        self.with_context(contract=True).onchange_employee()

    def get_salary_line_total(self, code):
        self.ensure_one()
        match = self.line_ids.filtered(lambda l: l.code == code)[:1]
        return match.total if match else 0.0

    @api.model
    def _hn_payroll_dashboard_action(self, xml_id, domain=None, extra_context=None):
        action = dict(self.env["ir.actions.act_window"]._for_xml_id(xml_id))
        if domain is not None:
            action["domain"] = domain
        if extra_context:
            ctx = action.get("context") or {}
            if isinstance(ctx, str):
                ctx = safe_eval(ctx, {"context": dict(self.env.context)})
            elif not isinstance(ctx, dict):
                ctx = {}
            action["context"] = {**ctx, **extra_context}
        return action

    @api.model
    def get_payroll_dashboard_data(self):
        """Devuelve tarjetas de seguimiento para el centro de nómina (Hub CE)."""
        today = fields.Date.today()
        company = self.env.company
        Employee = self.env["hr.employee"]

        def company_domain(base):
            if base and base[0] == "&":
                return ["&", ("company_id", "=", company.id)] + base
            return [("company_id", "=", company.id)] + base

        def in_payroll_contract():
            return [
                ("active", "=", True),
                ("contract_date_start", "!=", False),
                "|",
                ("contract_date_end", "=", False),
                ("contract_date_end", ">=", today),
            ]

        def not_in_payroll_contract():
            return [
                "&",
                ("active", "=", True),
                "|",
                ("contract_date_start", "=", False),
                "&",
                ("contract_date_end", "!=", False),
                ("contract_date_end", "<", today),
            ]

        items = []

        struct_count = self.env["hr.payroll.structure"].search_count(
            [("company_id", "=", company.id)]
        )
        if not struct_count:
            items.append(
                {
                    "key": "no_structures",
                    "accent": "purple",
                    "title": _("Create a salary structure"),
                    "subtitle": _(
                        "Define at least one structure before running payslips for this company."
                    ),
                    "button_label": _("Salary structures"),
                    "action": self._hn_payroll_dashboard_action(
                        "l10n_hn_payroll_base.action_hr_payroll_structure"
                    ),
                }
            )

        tpl_count = self.env["hr.version.advantage.template"].search_count([])
        if struct_count and not tpl_count:
            items.append(
                {
                    "key": "no_benefit_templates",
                    "accent": "pink",
                    "title": _("Configure contract benefits"),
                    "subtitle": _(
                        "Add advantage templates to capture extras and benefits on contracts."
                    ),
                    "button_label": _("Contract templates"),
                    "action": self._hn_payroll_dashboard_action(
                        "l10n_hn_payroll_base.action_hr_version_advantage_template"
                    ),
                }
            )

        domain_no_struct = company_domain(in_payroll_contract() + [("struct_id", "=", False)])
        n_no_struct = Employee.search_count(domain_no_struct)
        if n_no_struct:
            items.append(
                {
                    "key": "employees_no_structure",
                    "accent": "blue",
                    "title": _("%(count)s employees without salary structure", count=n_no_struct),
                    "subtitle": _(
                        "Assign a structure on the contract so payslips can be computed."
                    ),
                    "button_label": _("Review employees"),
                    "action": self._hn_payroll_dashboard_action(
                        "hr.open_view_employee_list_my",
                        domain=domain_no_struct,
                    ),
                }
            )

        domain_not_contract = company_domain(not_in_payroll_contract())
        n_not_contract = Employee.search_count(domain_not_contract)
        if n_not_contract:
            items.append(
                {
                    "key": "employees_no_contract",
                    "accent": "yellow",
                    "title": _("%(count)s employees without a current contract", count=n_not_contract),
                    "subtitle": _("Update contract dates so payroll can link the right version."),
                    "button_label": _("Open employees"),
                    "action": self._hn_payroll_dashboard_action(
                        "hr.open_view_employee_list_my",
                        domain=domain_not_contract,
                    ),
                }
            )

        domain_no_journal = company_domain(
            in_payroll_contract() + [("journal_id", "=", False)]
        )
        n_no_journal = Employee.search_count(domain_no_journal)
        if n_no_journal:
            items.append(
                {
                    "key": "employees_no_journal",
                    "accent": "cyan",
                    "title": _("%(count)s employees without salary journal", count=n_no_journal),
                    "subtitle": _(
                        "Pick the accrual journal used when payslips are posted to accounting."
                    ),
                    "button_label": _("Review employees"),
                    "action": self._hn_payroll_dashboard_action(
                        "hr.open_view_employee_list_my",
                        domain=domain_no_journal,
                    ),
                }
            )

        domain_no_bank = company_domain(in_payroll_contract() + [("bank_account_ids", "=", False)])
        n_no_bank = Employee.search_count(domain_no_bank)
        if n_no_bank:
            items.append(
                {
                    "key": "employees_no_bank",
                    "accent": "orange",
                    "title": _("%(count)s employees missing bank account", count=n_no_bank),
                    "subtitle": _(
                        "Bank details are required to pay net wages by transfer in most setups."
                    ),
                    "button_label": _("Set bank details"),
                    "action": self._hn_payroll_dashboard_action(
                        "hr.open_view_employee_list_my",
                        domain=domain_no_bank,
                    ),
                }
            )

        id_domain = Domain.AND(
            [
                Domain(company_domain(in_payroll_contract())),
                Domain(
                    [
                        "&",
                        "|",
                        ("barcode", "=", False),
                        ("barcode", "=", ""),
                        "|",
                        ("work_contact_id", "=", False),
                        ("work_contact_id.vat", "in", [False, ""]),
                    ]
                ),
            ]
        )
        n_no_id = Employee.search_count(id_domain)
        if n_no_id:
            items.append(
                {
                    "key": "employees_no_id",
                    "accent": "teal",
                    "title": _("%(count)s employees missing identification (VAT or badge)", count=n_no_id),
                    "subtitle": _(
                        "Complete tax ID on the work contact or set a badge ID for each employee."
                    ),
                    "button_label": _("Configure IDs"),
                    "action": self._hn_payroll_dashboard_action(
                        "hr.open_view_employee_list_my",
                        domain=list(id_domain),
                    ),
                }
            )

        domain_draft = [("company_id", "=", company.id), ("state", "=", "draft")]
        n_draft = self.search_count(domain_draft)
        if n_draft:
            items.append(
                {
                    "key": "payslips_draft",
                    "accent": "blue",
                    "title": _("%(count)s draft payslips", count=n_draft),
                    "subtitle": _("Compute, review and validate slips that are still in draft."),
                    "button_label": _("Open payslips"),
                    "action": self._hn_payroll_dashboard_action(
                        "l10n_hn_payroll_base.action_view_hr_payslip_form",
                        domain=domain_draft,
                    ),
                }
            )

        domain_verify = [("company_id", "=", company.id), ("state", "=", "verify")]
        n_verify = self.search_count(domain_verify)
        if n_verify:
            items.append(
                {
                    "key": "payslips_waiting",
                    "accent": "blue",
                    "title": _("%(count)s payslips awaiting validation", count=n_verify),
                    "subtitle": _(
                        "These payslips were computed and are waiting for approval."
                    ),
                    "button_label": _("Review payslips"),
                    "action": self._hn_payroll_dashboard_action(
                        "l10n_hn_payroll_base.action_view_hr_payslip_form",
                        domain=domain_verify,
                    ),
                }
            )

        domain_batches = [("state", "=", "draft")]
        n_batches = self.env["hr.payslip.run"].search_count(domain_batches)
        if n_batches:
            items.append(
                {
                    "key": "batches_open",
                    "accent": "purple",
                    "title": _("%(count)s open payroll batches", count=n_batches),
                    "subtitle": _("Close batches once all slips are validated."),
                    "button_label": _("Open batches"),
                    "action": self._hn_payroll_dashboard_action(
                        "l10n_hn_payroll_base.action_hr_payslip_run_tree",
                        domain=domain_batches,
                    ),
                }
            )

        if "move_id" in self._fields:
            domain_no_move = [
                ("company_id", "=", company.id),
                ("state", "in", ("done", "paid")),
                ("move_id", "=", False),
            ]
            n_no_move = self.search_count(domain_no_move)
            if n_no_move:
                items.append(
                    {
                        "key": "payslips_no_move",
                        "accent": "yellow",
                        "title": _("%(count)s validated payslips without accounting entry", count=n_no_move),
                        "subtitle": _(
                            "Accounting entries are created when payslips are validated; "
                            "check journal and salary rules."
                        ),
                        "button_label": _("Review payslips"),
                        "action": self._hn_payroll_dashboard_action(
                            "l10n_hn_payroll_base.action_view_hr_payslip_form",
                            domain=domain_no_move,
                        ),
                    }
                )

        emphasis_keys = {
            "employees_no_contract",
            "employees_no_bank",
            "employees_no_id",
            "payslips_no_move",
        }
        for row in items:
            row["variant"] = "emphasis" if row.get("key") in emphasis_keys else "default"

        return {"section_title": _("Today"), "items": items}


class HrPayslipLine(models.Model):
    _name = "hr.payslip.line"
    _inherit = "hr.salary.rule"
    _description = "Payslip Line"
    _order = "contract_id, sequence, id"

    slip_id = fields.Many2one("hr.payslip", required=True, ondelete="cascade", index=True)
    salary_rule_id = fields.Many2one("hr.salary.rule", required=True, ondelete="restrict")
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    contract_id = fields.Many2one("hr.version", required=True, ondelete="cascade", index=True)
    rate = fields.Float(string="Rate (%)", digits="HN Payroll Rate", default=100.0)
    amount = fields.Float(digits="HN Payroll")
    quantity = fields.Float(digits="HN Payroll", default=1.0)
    total = fields.Float(compute="_compute_total", digits="HN Payroll", store=True)

    @api.depends("quantity", "amount", "rate")
    def _compute_total(self):
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            payslip = self.env["hr.payslip"].browse(vals.get("slip_id"))
            vals.setdefault("employee_id", payslip.employee_id.id)
            vals.setdefault("contract_id", payslip.contract_id.id)
            if not vals.get("contract_id"):
                raise UserError(_("Each payslip line requires a contract."))
        return super().create(vals_list)


class HrPayslipWorkedDays(models.Model):
    _name = "hr.payslip.worked_days"
    _description = "Payslip Worked Days"
    _order = "payslip_id, sequence, id"

    name = fields.Char(required=True)
    payslip_id = fields.Many2one("hr.payslip", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(required=True, default=10)
    code = fields.Char(required=True, help="Code used in salary rules.")
    work_entry_type_id = fields.Many2one(
        "hr.work.entry.type",
        string="Work Entry Type",
        ondelete="set null",
        index=True,
    )
    number_of_days = fields.Float()
    number_of_hours = fields.Float()
    contract_id = fields.Many2one("hr.version", required=True, ondelete="cascade")
    currency_id = fields.Many2one(
        "res.currency",
        related="payslip_id.currency_id",
        readonly=True,
    )
    amount = fields.Monetary(
        string="Amount",
        compute="_compute_worked_days_amount",
        currency_field="currency_id",
    )

    @api.depends(
        "number_of_days",
        "payslip_id",
        "payslip_id.basic_wage",
        "payslip_id.total_worked_days",
        "payslip_id.worked_days_line_ids.number_of_days",
    )
    def _compute_worked_days_amount(self):
        for line in self:
            slip = line.payslip_id
            total_days = slip.total_worked_days or 0.0
            basic = slip.basic_wage or 0.0
            ndays = line.number_of_days or 0.0
            if total_days and ndays:
                line.amount = basic * (ndays / total_days)
            elif len(slip.worked_days_line_ids) == 1 and ndays:
                line.amount = basic
            else:
                line.amount = 0.0


class HrPayslipInput(models.Model):
    _name = "hr.payslip.input"
    _description = "Payslip Input"
    _order = "payslip_id, sequence, id"

    name = fields.Char(required=True)
    payslip_id = fields.Many2one("hr.payslip", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(required=True, default=10)
    input_type_id = fields.Many2one(
        "hr.payslip.input.type",
        string="Type",
        domain="[('id', 'in', allowed_input_type_ids)]",
    )
    allowed_input_type_ids = fields.Many2many(
        "hr.payslip.input.type",
        compute="_compute_allowed_input_type_ids",
    )
    code = fields.Char(required=True)
    amount = fields.Float()
    contract_id = fields.Many2one("hr.version", required=True, ondelete="cascade")

    @api.depends("payslip_id.struct_id", "payslip_id.struct_id.input_line_type_ids")
    def _compute_allowed_input_type_ids(self):
        InputType = self.env["hr.payslip.input.type"]
        for line in self:
            struct = line.payslip_id.struct_id if line.payslip_id else self.env["hr.payroll.structure"]
            if struct and struct.input_line_type_ids:
                line.allowed_input_type_ids = struct.input_line_type_ids
            else:
                line.allowed_input_type_ids = InputType.search([("active", "=", True)])

    @api.onchange("input_type_id")
    def _onchange_input_type_id(self):
        if self.input_type_id:
            self.code = self.input_type_id.code
            self.name = self.input_type_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            it_id = vals.get("input_type_id")
            if it_id:
                it = self.env["hr.payslip.input.type"].browse(it_id)
                vals.setdefault("code", it.code)
                vals.setdefault("name", it.name)
        return super().create(vals_list)


class HrPayslipRun(models.Model):
    _name = "hr.payslip.run"
    _description = "Payslip Batch"

    name = fields.Char(required=True)
    slip_ids = fields.One2many("hr.payslip", "payslip_run_id", string="Payslips")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Done"),
            ("paid", "Paid"),
        ],
        default="draft",
        copy=False,
    )
    structure_id = fields.Many2one("hr.payroll.structure", string="Salary Structure")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )
    country_id = fields.Many2one(
        "res.country",
        string="Country",
        related="company_id.country_id",
        store=True,
        readonly=True,
    )
    country_code = fields.Char(related="country_id.code", readonly=True, store=True)
    schedule_pay = fields.Selection(
        selection=lambda self: self.env["hr.payroll.structure.type"]._get_selection_schedule_pay(),
        string="Pay Schedule",
        default="monthly",
    )
    date_start = fields.Date(
        required=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)),
    )
    date_end = fields.Date(
        required=True,
        default=lambda self: fields.Date.to_string(
            (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
        ),
    )
    credit_note = fields.Boolean(
        string="Credit Note",
        help="Generated slips are refunds.",
    )
    slip_count = fields.Integer(compute="_compute_slip_count")
    payslip_count = fields.Integer(compute="_compute_slip_count")
    employee_count = fields.Integer(compute="_compute_employee_count", string="Employees")
    payrun_period_summary = fields.Char(
        string="Period summary",
        compute="_compute_payrun_period_summary",
    )
    payrun_progress_payload = fields.Json(
        string="Pay run progress",
        compute="_compute_payrun_progress_payload",
    )
    payrun_total_employer_cost = fields.Monetary(
        string="Employer cost",
        compute="_compute_payrun_financial_totals",
        currency_field="currency_id",
    )
    payrun_total_gross = fields.Monetary(
        string="Gross",
        compute="_compute_payrun_financial_totals",
        currency_field="currency_id",
    )
    payrun_total_net = fields.Monetary(
        string="Net",
        compute="_compute_payrun_financial_totals",
        currency_field="currency_id",
    )

    def _compute_slip_count(self):
        for rec in self:
            n = len(rec.slip_ids)
            rec.slip_count = n
            rec.payslip_count = n

    @api.depends("slip_ids.employee_id")
    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec.slip_ids.employee_id)

    @api.depends("date_start", "date_end")
    def _compute_payrun_period_summary(self):
        for rec in self:
            ds, de = rec.date_start, rec.date_end
            if not ds or not de:
                rec.payrun_period_summary = ""
                continue
            env = rec.env
            same_year = ds.year == de.year
            fmt = "MMM d" if same_year else "MMM d, y"
            left = format_date(env, ds, date_format=fmt)
            right = format_date(env, de, date_format=fmt)
            rec.payrun_period_summary = _("%(start)s → %(end)s", start=left, end=right)

    @api.depends(
        "slip_ids",
        "slip_ids.gross_wage",
        "slip_ids.payslip_net_total",
        "slip_ids.line_ids.total",
        "slip_ids.line_ids.category_id",
    )
    def _compute_payrun_financial_totals(self):
        for rec in self:
            slips = rec.slip_ids
            gross = sum(slips.mapped("gross_wage"))
            net = sum(slips.mapped("payslip_net_total"))
            comp = 0.0
            for slip in slips:
                for line in slip.line_ids:
                    code = line.category_id.code if line.category_id else ""
                    if code == "COMP":
                        comp += line.total or 0.0
            rec.payrun_total_gross = gross
            rec.payrun_total_net = net
            rec.payrun_total_employer_cost = gross + comp

    @api.depends("state", "slip_ids")
    def _compute_payrun_progress_payload(self):
        for rec in self:
            if rec.state == "paid":
                st_emp = st_time = st_slip = "done"
                palette = "paid"
            elif rec.state == "done":
                st_emp = st_time = st_slip = "done"
                palette = "done"
            elif rec.slip_ids:
                st_emp = "done"
                st_time = "done"
                st_slip = "active"
                palette = "done"
            else:
                st_emp = "active"
                st_time = st_slip = "pending"
                palette = "draft"
            rec.payrun_progress_payload = {
                "palette": palette,
                "steps": [
                    {"label": _("Employees"), "stage": st_emp},
                    {"label": _("Time"), "stage": st_time},
                    {"label": _("Payslips"), "stage": st_slip},
                ],
            }

    @api.model
    def _get_name_for_period(self, vals=None, cache=None):
        if vals is None:
            vals = {}
        if not vals.get("date_start") or not vals.get("date_end"):
            raise UserError(self.env._("You must set a start and end date for the Pay Run"))
        ds = vals["date_start"]
        de = vals["date_end"]
        if isinstance(ds, str):
            ds = fields.Date.from_string(ds)
        if isinstance(de, str):
            de = fields.Date.from_string(de)
        name = "%s – %s" % (ds, de)
        sid = vals.get("structure_id")
        if sid:
            struct = self.env["hr.payroll.structure"].browse(sid)
            name = "%s – %s" % (name, struct.name)
        return name

    def _get_valid_version_ids(
        self,
        date_start=None,
        date_end=None,
        structure_id=None,
        company_id=None,
        employee_ids=None,
        schedule_pay=None,
    ):
        """Lógica equivalente a hr_payroll Enterprise (contratos por período)."""
        date_start = date_start or self.date_start
        date_end = date_end or self.date_end
        structure = (
            self.env["hr.payroll.structure"].browse(structure_id)
            if structure_id
            else self.structure_id
        )
        schedule_pay = schedule_pay or self.schedule_pay
        company = company_id or self.company_id.id
        version_domain = Domain(
            [
                ("company_id", "=", company),
                ("employee_id", "!=", False),
                ("active_employee", "=", True),
                ("contract_date_start", "<=", date_end),
                "|",
                ("contract_date_end", "=", False),
                ("contract_date_end", ">=", date_start),
                ("date_version", "<=", date_end),
                ("structure_type_id", "!=", False),
            ]
        )
        if structure and structure.type_id:
            version_domain &= Domain([("structure_type_id", "=", structure.type_id.id)])
        if structure and structure.restricted_contract_type_ids:
            version_domain &= Domain(
                [("contract_type_id", "in", structure.restricted_contract_type_ids.ids)]
            )
        if employee_ids:
            version_domain &= Domain([("employee_id", "in", employee_ids)])
        if schedule_pay:
            version_domain &= Domain([("schedule_pay", "=", schedule_pay)])
        all_versions = self.env["hr.version"]._read_group(
            domain=version_domain,
            groupby=["employee_id", "date_version:day"],
            order="date_version:day DESC",
            aggregates=["id:recordset"],
        )
        all_employee_versions = defaultdict(list)
        for employee, _dv, version in all_versions:
            all_employee_versions[employee] += [*version]
        valid_versions = self.env["hr.version"]
        for employee_versions in all_employee_versions.values():
            employee_valid_versions = self.env["hr.version"]
            for i in range(len(employee_versions)):
                version = employee_versions[i]
                if version.date_version <= date_start or employee_versions[-1] == version:
                    employee_valid_versions |= version
                    break
                if employee_valid_versions:
                    if (
                        employee_valid_versions[-1].contract_date_start > version.contract_date_start
                        and (
                            version.contract_date_start >= version.date_version
                            or version.contract_date_start
                            > employee_versions[i + 1].contract_date_start
                        )
                    ):
                        employee_valid_versions |= version
                elif version.contract_date_start >= version.date_version or (
                    version.contract_date_start > employee_versions[i + 1].contract_date_start
                ):
                    employee_valid_versions |= version
            valid_versions |= employee_valid_versions
        return valid_versions.ids

    @api.onchange("structure_id")
    def _onchange_payroll_run_structure_id(self):
        if not self.structure_id:
            return
        self.schedule_pay = (
            self.structure_id.schedule_pay
            or (
                self.structure_id.type_id.default_schedule_pay
                if self.structure_id.type_id
                else False
            )
            or "monthly"
        )

    @api.model_create_multi
    def create(self, vals_list):
        cache = {}
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self._get_name_for_period(vals, cache)
        return super().create(vals_list)

    def action_payroll_hr_version_list_view_payrun(
        self,
        date_start=None,
        date_end=None,
        structure_id=None,
        company_id=None,
        schedule_pay=None,
    ):
        self.ensure_one()
        valid_version_ids = self._get_valid_version_ids(
            date_start=date_start,
            date_end=date_end,
            structure_id=structure_id,
            company_id=company_id,
            employee_ids=None,
            schedule_pay=schedule_pay,
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_hn_payroll_base.action_hr_version_payrun_select"
        )
        action["domain"] = [("id", "in", valid_version_ids)]
        return action

    def draft_payslip_run(self):
        return self.write({"state": "draft"})

    def close_payslip_run(self):
        """Complete processing for this pay run (historical method name kept for extensions)."""
        return self.write({"state": "done"})

    def action_payslip_run_mark_paid(self):
        not_done = self.filtered(lambda r: r.state != "done")
        if not_done:
            raise UserError(_("Only pay runs in Done can be marked as paid."))
        return self.write({"state": "paid"})
