# -*- coding: utf-8 -*-
"""Accounting bridge: payslip validation generates posted journal entries."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    def _payroll_partner_for_line(self, credit_account):
        """Partner on move line when register or account type requires it."""
        self.ensure_one()
        rule = self.salary_rule_id
        register_partner = rule.register_id.partner_id
        partner = register_partner or self.slip_id.employee_id.address_home_id
        if credit_account:
            if register_partner or rule.account_credit.account_type in ("asset_receivable", "liability_payable"):
                return partner.id if partner else False
        else:
            if register_partner or rule.account_debit.account_type in ("asset_receivable", "liability_payable"):
                return partner.id if partner else False
        return False


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    date = fields.Date(
        string="Accounting Date",
        readonly=False,
        help="If empty, the payslip period end date is used.",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Salary Journal",
        readonly=False,
        required=True,
        default=lambda self: self.env["account.journal"].search([("type", "=", "general")], limit=1),
    )
    move_id = fields.Many2one("account.move", string="Accounting Entry", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        journal_from_ctx = self.env.context.get("journal_id")
        Struct = self.env["hr.payroll.structure"]
        for vals in vals_list:
            if journal_from_ctx:
                vals.setdefault("journal_id", journal_from_ctx)
            if not vals.get("journal_id"):
                sid = vals.get("struct_id")
                if sid:
                    struct = Struct.browse(sid)
                    if struct.journal_id:
                        vals["journal_id"] = struct.journal_id.id
        return super().create(vals_list)

    @api.onchange("contract_id")
    def onchange_contract(self):
        super().onchange_contract()
        if self.contract_id and getattr(self.contract_id, "journal_id", False):
            self.journal_id = self.contract_id.journal_id
        elif self.contract_id and self.contract_id.struct_id and self.contract_id.struct_id.journal_id:
            self.journal_id = self.contract_id.struct_id.journal_id

    def action_payslip_cancel(self):
        for slip in self:
            move = slip.move_id
            if move:
                move.button_cancel()
                move.unlink()
        return super().action_payslip_cancel()

    def action_payslip_done(self):
        res = super().action_payslip_done()
        for slip in self:
            slip._create_payroll_account_move()
        return res

    def _create_payroll_account_move(self):
        self.ensure_one()
        if self.move_id:
            return self.move_id
        line_commands = []
        debit_sum = credit_sum = 0.0
        slip_date = self.date or self.date_to
        currency = self.company_id.currency_id
        name = _("Payslip of %s") % self.employee_id.name
        for line in self.details_by_salary_rule_category:
            amount = currency.round((-line.total) if self.credit_note else line.total)
            if currency.is_zero(amount):
                continue
            debit_account = line.salary_rule_id.account_debit
            credit_account = line.salary_rule_id.account_credit
            if debit_account:
                deb = amount > 0.0 and amount or 0.0
                cred = amount < 0.0 and -amount or 0.0
                tax_vals = {}
                if line.salary_rule_id.account_tax_id:
                    tax_vals["tax_ids"] = [(6, 0, [line.salary_rule_id.account_tax_id.id])]
                line_commands.append(
                    (
                        0,
                        0,
                        {
                            "name": line.name,
                            "partner_id": line._payroll_partner_for_line(credit_account=False),
                            "account_id": debit_account.id,
                            "journal_id": self.journal_id.id,
                            "date": slip_date,
                            "debit": deb,
                            "credit": cred,
                            **tax_vals,
                        },
                    )
                )
                debit_sum += deb - cred
            if credit_account:
                deb = amount < 0.0 and -amount or 0.0
                cred = amount > 0.0 and amount or 0.0
                tax_vals = {}
                if line.salary_rule_id.account_tax_id:
                    tax_vals["tax_ids"] = [(6, 0, [line.salary_rule_id.account_tax_id.id])]
                line_commands.append(
                    (
                        0,
                        0,
                        {
                            "name": line.name,
                            "partner_id": line._payroll_partner_for_line(credit_account=True),
                            "account_id": credit_account.id,
                            "journal_id": self.journal_id.id,
                            "date": slip_date,
                            "debit": deb,
                            "credit": cred,
                            **tax_vals,
                        },
                    )
                )
                credit_sum += cred - deb
        if not line_commands:
            return self.env["account.move"]
        suspense = self.journal_id.default_account_id
        if not suspense:
            raise UserError(
                _("Journal %(journal)s has no default account for rounding adjustments.")
                % {"journal": self.journal_id.display_name}
            )
        if currency.compare_amounts(credit_sum, debit_sum) < 0:
            line_commands.append(
                (
                    0,
                    0,
                    {
                        "name": _("Rounding adjustment"),
                        "account_id": suspense.id,
                        "journal_id": self.journal_id.id,
                        "date": slip_date,
                        "debit": 0.0,
                        "credit": currency.round(debit_sum - credit_sum),
                    },
                )
            )
        elif currency.compare_amounts(debit_sum, credit_sum) < 0:
            line_commands.append(
                (
                    0,
                    0,
                    {
                        "name": _("Rounding adjustment"),
                        "account_id": suspense.id,
                        "journal_id": self.journal_id.id,
                        "date": slip_date,
                        "debit": currency.round(credit_sum - debit_sum),
                        "credit": 0.0,
                    },
                )
            )
        move = self.env["account.move"].create(
            {
                "narration": name,
                "ref": self.number,
                "journal_id": self.journal_id.id,
                "date": slip_date,
                "line_ids": line_commands,
            }
        )
        move.action_post()
        self.write({"move_id": move.id, "date": slip_date})
        return move


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    account_tax_id = fields.Many2one("account.tax", string="Tax")
    account_debit = fields.Many2one("account.account", string="Debit Account")
    account_credit = fields.Many2one("account.account", string="Credit Account")


class HrVersion(models.Model):
    _inherit = "hr.version"

    journal_id = fields.Many2one("account.journal", string="Salary Journal")


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    journal_id = fields.Many2one(
        related="version_id.journal_id",
        readonly=False,
        inherited=True,
        groups="hr.group_hr_user",
    )


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    journal_id = fields.Many2one(
        "account.journal",
        string="Salary Journal",
        readonly=False,
        required=True,
        default=lambda self: self.env["account.journal"].search([("type", "=", "general")], limit=1),
    )
