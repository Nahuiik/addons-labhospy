# -*- coding: utf-8 -*-
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PayslipLinesContributionRegister(models.TransientModel):
    _name = "payslip.lines.contribution.register"
    _description = "Contribution register date range"

    date_from = fields.Date(required=True, default=lambda _: fields.Date.today().replace(day=1))
    date_to = fields.Date(
        required=True,
        default=lambda _: fields.Date.to_date(datetime.now() + relativedelta(months=1, day=1, days=-1)),
    )

    def print_report(self):
        self.ensure_one()
        data = {"ids": self.env.context.get("active_ids", []), "model": "hr.contribution.register", "form": self.read()[0]}
        return self.env.ref("l10n_hn_payroll_base.action_report_contribution_register").report_action([], data=data)
