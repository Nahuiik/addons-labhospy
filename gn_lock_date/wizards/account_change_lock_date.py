# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.account.models.company import LOCK_DATE_FIELDS


class AccountChangeLockDate(models.TransientModel):
    _name = "account.change.lock.date"
    _description = "Update Accounting Lock Dates"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    fiscalyear_lock_date = fields.Date(string="Global Lock Date")
    tax_lock_date = fields.Date(string="Tax Return Lock Date")
    sale_lock_date = fields.Date(string="Sales Lock Date")
    purchase_lock_date = fields.Date(string="Purchases Lock Date")
    hard_lock_date = fields.Date(string="Hard Lock Date")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        res.setdefault("company_id", company.id)
        for fname in LOCK_DATE_FIELDS:
            if not fields_list or fname in fields_list:
                res[fname] = company[fname]
        return res

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(
                _("Only users with the Adviser (Accounting Manager) role can update lock dates.")
            )
        company = self.company_id
        vals = {fname: self[fname] for fname in LOCK_DATE_FIELDS}
        to_write = {k: v for k, v in vals.items() if company[k] != v}
        if to_write:
            company.write(to_write)
        return {"type": "ir.actions.act_window_close"}
