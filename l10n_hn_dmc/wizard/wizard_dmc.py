# -*- coding: utf-8 -*-
from odoo import fields, models


class WizardDmcReport(models.TransientModel):
    _name = "l10n_hn_dmc.wizard_dmc_report"
    _description = "Reporte DMC"

    date_from = fields.Date(string="Fecha inicial", required=True)
    date_to = fields.Date(string="Fecha final", required=True)

    def print_report(self):
        self.ensure_one()
        data = {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "company_name": self.env.company.name,
        }
        return self.env.ref("l10n_hn_dmc.dmc_report_xls").report_action(
            False,
            data=data,
        )
