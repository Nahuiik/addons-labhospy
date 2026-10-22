# ©  2024 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details
# Updated: 2025-11-19 - Fixed domain issues for Odoo 19

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class StockValuationGenerateEntry(models.TransientModel):
    _name = "stock.valuation.generate.entry"
    _description = "Generate Accounting Entry from Stock Valuation"

    report_id = fields.Many2one("stock.valuation.report", string="Valuation Report", required=True)
    date = fields.Datetime(string="Entry Date", required=True)
    company_id = fields.Many2one("res.company", string="Company", required=True)
    stock_variation = fields.Monetary(
        string="Stock Variation",
        currency_field="company_currency_id",
        readonly=True,
    )
    ending_stock = fields.Monetary(
        string="Ending Stock",
        currency_field="company_currency_id",
        readonly=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        required=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
        help="Journal where the accounting entry will be created",
    )
    expense_account_id = fields.Many2one(
        "account.account",
        string="Expense Account",
        required=True,
        check_company=True,
        help="Account to use for stock variation (expense)",
    )
    stock_account_id = fields.Many2one(
        "account.account",
        string="Stock Valuation Account",
        required=True,
        check_company=True,
        help="Account to use for stock valuation",
    )
    move_id = fields.Many2one("account.move", string="Generated Entry", readonly=True)
    move_line_ids = fields.One2many(
        "stock.valuation.generate.entry.line",
        "wizard_id",
        string="Entry Lines",
        compute="_compute_move_lines",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "company_id" in fields_list:
            res["company_id"] = res.get("company_id") or self.env.company.id

        # Get default journal from company settings
        if "journal_id" in fields_list and not res.get("journal_id"):
            company = self.env["res.company"].browse(res.get("company_id") or self.env.company.id)
            if company.inventory_bridge_journal_id:
                res["journal_id"] = company.inventory_bridge_journal_id.id
            else:
                journal = self.env["account.journal"].search(
                    [("company_id", "=", company.id), ("type", "=", "general")], limit=1
                )
                if journal:
                    res["journal_id"] = journal.id

        # Get default accounts from company settings
        if "expense_account_id" in fields_list and not res.get("expense_account_id"):
            company = self.env["res.company"].browse(res.get("company_id") or self.env.company.id)
            if company.inventory_bridge_expense_account_id:
                res["expense_account_id"] = company.inventory_bridge_expense_account_id.id
            else:
                expense_account = self._get_default_expense_account(company.id)
                if expense_account:
                    res["expense_account_id"] = expense_account.id

        if "stock_account_id" in fields_list and not res.get("stock_account_id"):
            company = self.env["res.company"].browse(res.get("company_id") or self.env.company.id)
            if company.inventory_bridge_stock_account_id:
                res["stock_account_id"] = company.inventory_bridge_stock_account_id.id
            else:
                stock_account = self._get_default_stock_account(company.id)
                if stock_account:
                    res["stock_account_id"] = stock_account.id

        return res

    def _get_default_expense_account(self, company_id):
        """Get default expense account"""
        if not company_id:
            company_id = self.env.company.id

        company = self.env["res.company"].browse(company_id)
        
        # Try to get from product category
        categories = self.env["product.category"].search(
            [("property_stock_valuation_account_id", "!=", False)], limit=1
        )
        if categories:
            cogs_account = categories[0].property_account_expense_categ_id
            if cogs_account:
                # Verify account exists and use with_company to filter
                account = self.env["account.account"].with_company(company).browse(cogs_account.id)
                if account.exists():
                    return account

        # Fallback to company default expense account
        if company.chart_template_id:
            # Try to find a typical expense account (600000 pattern)
            # Use with_company instead of company_id in domain
            expense_accounts = self.env["account.account"].with_company(company).search(
                [
                    ("code", "=like", "6%"),
                    ("deprecated", "=", False),
                ],
                limit=1,
            )
            if expense_accounts:
                return expense_accounts[0]

        return False

    def _get_default_stock_account(self, company_id):
        """Get default stock valuation account"""
        if not company_id:
            company_id = self.env.company.id

        company = self.env["res.company"].browse(company_id)
        
        # Try to get from product category
        categories = self.env["product.category"].search(
            [("property_stock_valuation_account_id", "!=", False)], limit=1
        )
        if categories:
            stock_account = categories[0].property_stock_valuation_account_id
            if stock_account:
                # Verify account exists and use with_company to filter
                account = self.env["account.account"].with_company(company).browse(stock_account.id)
                if account.exists():
                    return account

        # Fallback to company default
        if company.stock_valuation_account_id:
            return company.stock_valuation_account_id

        # Try to find a typical stock account (110100 pattern)
        # Use with_company instead of company_id in domain
        stock_accounts = self.env["account.account"].with_company(company).search(
            [
                ("code", "=like", "11%"),
                ("deprecated", "=", False),
            ],
            limit=1,
        )
        if stock_accounts:
            return stock_accounts[0]

        return False

    @api.depends("stock_variation", "ending_stock", "expense_account_id", "stock_account_id")
    def _compute_move_lines(self):
        for wizard in self:
            lines = []
            if not wizard.expense_account_id or not wizard.stock_account_id:
                wizard.move_line_ids = False
                continue

            # Stock variation line (expense)
            if not float_is_zero(wizard.stock_variation, precision_digits=2):
                if wizard.stock_variation > 0:
                    # Debit expense, credit stock
                    lines.append(
                        (
                            0,
                            0,
                            {
                                "wizard_id": wizard.id,
                                "account_id": wizard.expense_account_id.id,
                                "debit": wizard.stock_variation,
                                "credit": 0.0,
                                "name": "Stock Variation",
                            },
                        )
                    )
                    lines.append(
                        (
                            0,
                            0,
                            {
                                "wizard_id": wizard.id,
                                "account_id": wizard.stock_account_id.id,
                                "debit": 0.0,
                                "credit": wizard.stock_variation,
                                "name": "Stock Variation",
                            },
                        )
                    )
                else:
                    # Credit expense, debit stock
                    lines.append(
                        (
                            0,
                            0,
                            {
                                "wizard_id": wizard.id,
                                "account_id": wizard.expense_account_id.id,
                                "debit": 0.0,
                                "credit": abs(wizard.stock_variation),
                                "name": "Stock Variation",
                            },
                        )
                    )
                    lines.append(
                        (
                            0,
                            0,
                            {
                                "wizard_id": wizard.id,
                                "account_id": wizard.stock_account_id.id,
                                "debit": abs(wizard.stock_variation),
                                "credit": 0.0,
                                "name": "Stock Variation",
                            },
                        )
                    )

            wizard.move_line_ids = lines

    @api.constrains("expense_account_id", "stock_account_id")
    def _check_accounts(self):
        for wizard in self:
            if wizard.expense_account_id and wizard.stock_account_id:
                if wizard.expense_account_id.id == wizard.stock_account_id.id:
                    raise ValidationError("Expense Account and Stock Account must be different")

    def action_generate_entry(self):
        """Generate the accounting entry"""
        self.ensure_one()

        if not self.journal_id:
            raise UserError("Please select a journal")

        if not self.expense_account_id or not self.stock_account_id:
            raise UserError("Please select both Expense Account and Stock Valuation Account")

        # Check if variation is zero - everything is correctly closed
        if float_is_zero(self.stock_variation, precision_digits=2):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Everything is correctly closed",
                    "message": "The inventory valuation is already balanced. No entry needs to be generated.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Check if an entry already exists for this period
        date_str = self.date.strftime('%Y-%m-%d') if self.date else ''
        existing_moves = self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('ref', '=like', f'Stock Valuation - {date_str}%'),
            ('state', '!=', 'cancel'),
        ], limit=1)
        
        if existing_moves:
            # Recompute report to check current variation
            if self.report_id:
                self.report_id._compute_valuation()
                # If variation is still zero after recompute, everything is closed
                if float_is_zero(self.report_id.stock_variation, precision_digits=2):
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": "Everything is correctly closed",
                            "message": "The inventory valuation is already balanced. No entry needs to be generated.",
                            "type": "warning",
                            "sticky": False,
                        },
                    }
            raise UserError("An accounting entry already exists for this period. Please check the existing entry.")

        # Create account move
        move_vals = {
            "move_type": "entry",
            "date": self.date.date(),
            "journal_id": self.journal_id.id,
            "company_id": self.company_id.id,
            "ref": f"Stock Valuation - {self.date.strftime('%Y-%m-%d')}",
            "line_ids": [],
        }

        # Add move lines
        for line in self.move_line_ids:
            move_vals["line_ids"].append(
                (
                    0,
                    0,
                    {
                        "account_id": line.account_id.id,
                        "debit": line.debit,
                        "credit": line.credit,
                        "name": line.name,
                    },
                )
            )

        # Create and post the move
        move = self.env["account.move"].create(move_vals)
        move.action_post()

        self.move_id = move.id
        
        # Recompute report after creating entry to reset values
        if self.report_id:
            self.report_id._compute_valuation()

        return {
            "name": "Generated Entry",
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": move.id,
            "target": "current",
        }


class StockValuationGenerateEntryLine(models.TransientModel):
    _name = "stock.valuation.generate.entry.line"
    _description = "Stock Valuation Generate Entry Line"

    wizard_id = fields.Many2one("stock.valuation.generate.entry", string="Wizard", required=True, ondelete="cascade")
    account_id = fields.Many2one("account.account", string="Account", required=True)
    debit = fields.Monetary(string="Debit", currency_field="company_currency_id", default=0.0)
    credit = fields.Monetary(string="Credit", currency_field="company_currency_id", default=0.0)
    name = fields.Char(string="Label", default="Stock Variation")
    company_currency_id = fields.Many2one(
        "res.currency",
        related="wizard_id.company_currency_id",
        string="Company Currency",
        readonly=True,
    )

