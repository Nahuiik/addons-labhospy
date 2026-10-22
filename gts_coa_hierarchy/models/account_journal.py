# -*- coding: utf-8 -*-
from odoo import api, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def _prepare_liquidity_account_vals(self, company, code, vals):
        res = super()._prepare_liquidity_account_vals(company=company, code=code, vals=vals)
        account_code_prefix = ""
        if res["account_type"] == "asset_cash":
            account_code_prefix = (
                company.cash_account_code_prefix or company.bank_account_code_prefix or ""
            )
        if account_code_prefix:
            parent_account = (
                self.env["account.account"]
                .with_company(company)
                .with_context(show_parent_account=True)
                .search(
                    [
                        ("code", "=", account_code_prefix),
                        ("account_type", "=", "view"),
                    ],
                    limit=1,
                )
            )
            if parent_account:
                res["parent_id"] = parent_account.id
        return res
