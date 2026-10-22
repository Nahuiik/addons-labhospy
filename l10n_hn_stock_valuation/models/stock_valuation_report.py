# ©  2024 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

import logging
from datetime import datetime, timedelta, time
from odoo import api, fields, models, Command
from odoo.tools import float_compare, float_is_zero
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockValuationReport(models.TransientModel):
    _name = "stock.valuation.report"
    _description = "Stock Valuation Report"

    name = fields.Char(string="Name", compute="_compute_name", store=False)
    
    @api.depends("date")
    def _compute_name(self):
        for report in self:
            if report.date:
                report.name = f"Stock Valuation - {report.date.strftime('%Y-%m-%d')}"
            else:
                report.name = "Stock Valuation"
    
    @api.model
    def default_get(self, fields_list):
        """Set default values and compute initial values"""
        res = super().default_get(fields_list)
        # Ensure company is set
        if 'company_id' not in res or not res.get('company_id'):
            res['company_id'] = self.env.company.id
        # Ensure date is set
        if 'date' not in res or not res.get('date'):
            res['date'] = fields.Date.today()
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure computation after creation"""
        records = super().create(vals_list)
        # Force computation of computed fields after creation
        for record in records:
            # Access the computed fields to trigger computation
            _ = record.initial_balance
            _ = record.ending_stock
            _ = record.stock_variation
            _ = record.valuation_line_ids
        return records

    date = fields.Date(
        string="Date",
        default=fields.Date.today,
        required=True,
        help="Date for the stock valuation",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    initial_balance = fields.Monetary(
        string="Initial Balance",
        compute="_compute_valuation",
        store=False,
        currency_field="company_currency_id",
    )
    stock_variation = fields.Monetary(
        string="Stock Variation",
        compute="_compute_valuation",
        store=False,
        currency_field="company_currency_id",
    )
    ending_stock = fields.Monetary(
        string="Ending Stock",
        compute="_compute_valuation",
        store=False,
        currency_field="company_currency_id",
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
    )
    valuation_line_ids = fields.One2many(
        "stock.valuation.report.line",
        "report_id",
        string="Valuation Lines",
        compute="_compute_valuation",
        store=False,
    )

    @api.onchange("date", "company_id")
    def _onchange_date(self):
        """Trigger recomputation when date or company change"""
        # Only compute if report has an ID (is saved)
        # For unsaved records, computation will happen when fields are accessed
        if self.id and self.date and self.company_id:
            self._compute_valuation()

    @api.depends("date", "company_id")
    def _compute_valuation(self):
        for report in self:
            # Initialize to 0 first
            report.initial_balance = 0.0
            report.stock_variation = 0.0
            report.ending_stock = 0.0
            
            # Delete existing lines if any (for computed One2many, we can't assign empty list)
            if report.valuation_line_ids:
                report.valuation_line_ids.unlink()
            
            if not report.date or not report.company_id:
                continue

            # Use date as report_date for ending stock calculation (end of day)
            report_date = report.date
            # Initial balance is calculated at the end of previous day
            date_from = report_date - timedelta(days=1) if report_date else None
            # Convert report_date to datetime at end of day for stock_value calculation
            report_datetime = datetime.combine(report_date, time.max) if report_date else None

            # Initialize variables
            inventory_data = {}
            initial_inventory_data = {}
            
            # Use company method stock_value() which is the standard Odoo method
            # This method internally uses product.with_context(to_date=at_date).total_value
            # and groups by stock valuation account
            # It returns a dict (or defaultdict): {account: value}
            try:
                if hasattr(report.company_id, 'stock_value'):
                    # Get stock value at the end date using company method
                    # Convert to regular dict to avoid defaultdict issues
                    inventory_data_raw = report.company_id.with_company(report.company_id).stock_value(at_date=report_datetime)
                    inventory_data = dict(inventory_data_raw) if inventory_data_raw else {}
                    ending_stock_value = sum(inventory_data.values()) if inventory_data else 0.0
                    report.ending_stock = ending_stock_value
                    
                    # Calculate initial balance (at end of previous day)
                    if date_from:
                        # Use end of previous day for initial balance
                        date_from_end = datetime.combine(date_from, time.max)
                        initial_inventory_data_raw = report.company_id.with_company(report.company_id).stock_value(at_date=date_from_end)
                        initial_inventory_data = dict(initial_inventory_data_raw) if initial_inventory_data_raw else {}
                        initial_balance_value = sum(initial_inventory_data.values()) if initial_inventory_data else 0.0
                        report.initial_balance = initial_balance_value
                    else:
                        report.initial_balance = 0.0
                        initial_inventory_data = {}
                else:
                    # Fallback if method doesn't exist
                    inventory_data = {}
                    initial_inventory_data = {}
                    report.ending_stock = 0.0
                    report.initial_balance = 0.0
            except Exception as e:
                # If company method fails, log the error
                _logger.error(f"[Stock Valuation] Error in _compute_valuation: {e}", exc_info=True)
                inventory_data = {}
                initial_inventory_data = {}
                report.ending_stock = 0.0
                report.initial_balance = 0.0
                # If company method fails, use direct calculation from products
                # Fallback: Calculate directly from products using to_date context
                # This is more reliable than using stock_value when it returns empty
                products = self.env['product.product'].with_company(report.company_id).search([
                    ('is_storable', '=', True),
                    ('type', '=', 'product'),
                ])
                
                # Calculate ending stock at report_date
                ending_stock_total = 0.0
                initial_stock_total = 0.0
                
                # Convert date to datetime for context (end of day)
                date_to_dt = report_datetime
                date_from_dt = datetime.combine(date_from, time.max) if date_from else None
                
                # Convert to string for context
                date_to_str = fields.Datetime.to_string(date_to_dt) if date_to_dt else None
                date_from_str = fields.Datetime.to_string(date_from_dt) if date_from_dt else None
                
                # Calculate ending stock - use to_date context
                # Use sudo to ensure we can read all products and their values
                products_sudo = products.sudo()
                for product in products_sudo:
                    try:
                        # Use with_company to ensure correct company context
                        product_with_date = product.with_company(report.company_id).with_context(
                            to_date=date_to_str,
                            company=report.company_id.id
                        )
                        # Access total_value which will be computed automatically
                        # The field depends on context 'to_date', so it should recalculate
                        product_value = product_with_date.total_value or 0.0
                        ending_stock_total += product_value
                    except Exception as e:
                        # If computation fails, try without date context
                        try:
                            product_value = product.with_company(report.company_id).total_value or 0.0
                            ending_stock_total += product_value
                        except Exception:
                            pass
                
                # Calculate initial balance
                if date_from_str:
                    for product in products_sudo:
                        try:
                            # Use with_company to ensure correct company context
                            product_with_date = product.with_company(report.company_id).with_context(
                                to_date=date_from_str,
                                company=report.company_id.id
                            )
                            # Access total_value which will be computed automatically
                            product_value = product_with_date.total_value or 0.0
                            initial_stock_total += product_value
                        except Exception:
                            # If computation fails, try without date context
                            try:
                                product_value = product.with_company(report.company_id).total_value or 0.0
                                initial_stock_total += product_value
                            except Exception:
                                pass
                else:
                    initial_stock_total = 0.0
                
                report.ending_stock = ending_stock_total
                report.initial_balance = initial_stock_total

            # Calculate stock variation (difference)
            report.stock_variation = report.ending_stock - report.initial_balance

            # Create valuation lines grouped by account
            lines = []
            account_lines = {}

            # Use inventory_data if available (from company methods)
            if inventory_data:
                # Create lines from inventory_data (ending stock)
                for account, value in inventory_data.items():
                    if account and not float_is_zero(value, precision_digits=2):
                        account_key = account.id
                        if account_key not in account_lines:
                            account_lines[account_key] = {
                                "account_id": account.id,
                                "debit": 0.0,
                                "credit": 0.0,
                                "value": 0.0,
                            }
                        account_lines[account_key]["value"] = value
            else:
                # Fallback: If no inventory_data, try to get accounts from products
                # Group by stock valuation account from products
                products = self.env['product.product'].with_company(report.company_id).search([
                    ('is_storable', '=', True),
                    ('type', '=', 'product'),
                ])
                
                for product in products:
                    # Get stock valuation account from product category
                    account = product.categ_id.property_stock_valuation_account_id
                    if not account:
                        # Fallback to company default
                        account = report.company_id.stock_valuation_account_id
                    if not account:
                        continue
                    
                    # Calculate product value at report date
                    try:
                        product_with_date = product.with_company(report.company_id).with_context(
                            to_date=report_date,
                            company=report.company_id.id
                        )
                        product_value = product_with_date.total_value or 0.0
                    except Exception:
                        product_value = 0.0
                    
                    if not float_is_zero(product_value, precision_digits=2):
                        account_key = account.id
                        if account_key not in account_lines:
                            account_lines[account_key] = {
                                "account_id": account.id,
                                "debit": 0.0,
                                "credit": 0.0,
                                "value": 0.0,
                            }
                        account_lines[account_key]["value"] += product_value

            # Create lines for ending stock
            # Only create lines if report has an ID (is saved)
            # For unsaved records, lines will be created after save
            if report.id:
                line_model = self.env['stock.valuation.report.line']
                # Delete existing lines first
                if report.valuation_line_ids:
                    report.valuation_line_ids.unlink()
                
                for account_key, vals in account_lines.items():
                    if not float_is_zero(vals["value"], precision_digits=2):
                        line_model.create({
                            "report_id": report.id,
                            "account_id": vals["account_id"],
                            "line_type": "ending",
                            "debit": vals["value"] if vals["value"] > 0 else 0.0,
                            "credit": abs(vals["value"]) if vals["value"] < 0 else 0.0,
                            "value": vals["value"],
                        })

            # Create lines for stock variation
            if not float_is_zero(report.stock_variation, precision_digits=2):
                # Get expense account from product category or company
                expense_account = self._get_expense_account()
                # Get stock account (use first account from ending stock or get default)
                stock_account = False
                if account_lines:
                    stock_account = self.env["account.account"].browse(list(account_lines.keys())[0])
                else:
                    # Try to get from product category
                    categories = self.env["product.category"].search(
                        [("property_stock_valuation_account_id", "!=", False)], limit=1
                    )
                    if categories:
                        stock_account = categories[0].property_stock_valuation_account_id
                    if not stock_account:
                        stock_account = report.company_id.stock_valuation_account_id

                if expense_account and stock_account and report.id:
                    line_model = self.env['stock.valuation.report.line']
                    # Expense line (debit if positive variation, credit if negative)
                    if report.stock_variation > 0:
                        line_model.create({
                            "report_id": report.id,
                            "account_id": expense_account.id,
                            "line_type": "variation",
                            "debit": report.stock_variation,
                            "credit": 0.0,
                            "value": report.stock_variation,
                        })
                        # Stock account line (credit)
                        line_model.create({
                            "report_id": report.id,
                            "account_id": stock_account.id,
                            "line_type": "variation",
                            "debit": 0.0,
                            "credit": report.stock_variation,
                            "value": report.stock_variation,
                        })
                    else:
                        # Negative variation
                        line_model.create({
                            "report_id": report.id,
                            "account_id": expense_account.id,
                            "line_type": "variation",
                            "debit": 0.0,
                            "credit": abs(report.stock_variation),
                            "value": report.stock_variation,
                        })
                        # Stock account line (debit)
                        line_model.create({
                            "report_id": report.id,
                            "account_id": stock_account.id,
                            "line_type": "variation",
                            "debit": abs(report.stock_variation),
                            "credit": 0.0,
                            "value": report.stock_variation,
                        })

    def _get_expense_account(self):
        """Get the expense account for stock variation"""
        # Try to get from product category
        categories = self.env["product.category"].search(
            [("property_stock_valuation_account_id", "!=", False)], limit=1
        )
        if categories:
            # Use COGS account if available
            cogs_account = categories[0].property_account_expense_categ_id
            if cogs_account:
                return cogs_account

        # Fallback to company default expense account
        if self.company_id.chart_template_id:
            # Try to find a typical expense account (600000 pattern)
            expense_accounts = self.env["account.account"].search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("code", "=like", "6%"),
                    ("deprecated", "=", False),
                ],
                limit=1,
            )
            if expense_accounts:
                return expense_accounts[0]

        return False

    def action_compute(self):
        """Force recalculation of valuation"""
        self.ensure_one()
        # Invalidate cache for computed fields to force recalculation
        self.invalidate_recordset(['initial_balance', 'ending_stock', 'stock_variation', 'valuation_line_ids'])
        
        # Force recompute by calling the compute method directly
        self._compute_valuation()
        
        # Force flush to ensure values are written
        self.env.flush_all()
        
        # Return to form view to show updated values
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_generate_entry(self):
        """Open wizard to generate accounting entry"""
        self.ensure_one()
        
        # Recompute to get current values
        self._compute_valuation()
        
        # If variation is zero, everything is correctly closed
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
            # Entry already exists - warn user
            raise UserError(
                "An accounting entry already exists for this period. "
                "Please check the existing entry or select a different date range."
            )
        
        return {
            "name": "Generate Accounting Entry",
            "type": "ir.actions.act_window",
            "res_model": "stock.valuation.generate.entry",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_report_id": self.id,
                "default_date": fields.Datetime.combine(self.date, time.max) if self.date else fields.Datetime.now(),
                "default_company_id": self.company_id.id,
                "default_stock_variation": self.stock_variation,
                "default_ending_stock": self.ending_stock,
            },
        }


class StockValuationReportLine(models.TransientModel):
    _name = "stock.valuation.report.line"
    _description = "Stock Valuation Report Line"

    report_id = fields.Many2one("stock.valuation.report", string="Report", required=True, ondelete="cascade")
    account_id = fields.Many2one("account.account", string="Account", required=True)
    line_type = fields.Selection(
        [
            ("initial", "Initial Balance"),
            ("variation", "Stock Variation"),
            ("ending", "Ending Stock"),
        ],
        string="Line Type",
        required=True,
    )
    debit = fields.Monetary(string="Debit", currency_field="company_currency_id", default=0.0)
    credit = fields.Monetary(string="Credit", currency_field="company_currency_id", default=0.0)
    value = fields.Monetary(string="Value", currency_field="company_currency_id")
    company_currency_id = fields.Many2one(
        "res.currency",
        related="report_id.company_currency_id",
        string="Company Currency",
        readonly=True,
    )

