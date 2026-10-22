# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, models


class HrHistoricalSalaryIncreaseHn(models.Model):
    _inherit = "hr.historical.salary.increase"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._l10n_hn_bump_monthly_salary_history()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ("employee_id", "date")):
            self._l10n_hn_bump_monthly_salary_history()
        return res

    def unlink(self):
        refs = [(r.employee_id.id, r.date) for r in self if r.employee_id and r.date]
        res = super().unlink()
        Hist = self.env["l10n.hn.employee.monthly.salary.history"].sudo()
        for emp_id, d in refs:
            if not d:
                continue
            hs = Hist.search([
                ("employee_id", "=", emp_id),
                ("year", "=", d.year),
                ("month", "=", d.month),
            ])
            hs._compute_historical_increase_ids()
        return res

    def _l10n_hn_bump_monthly_salary_history(self):
        Hist = self.env["l10n.hn.employee.monthly.salary.history"].sudo()
        for rec in self:
            if not rec.employee_id or not rec.date:
                continue
            if getattr(rec.employee_id, "hn_company_country_code", None) != "HN":
                continue
            hs = Hist.search([
                ("employee_id", "=", rec.employee_id.id),
                ("year", "=", rec.date.year),
                ("month", "=", rec.date.month),
            ])
            hs._compute_historical_increase_ids()
