# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.tools.misc import formatLang


class ReportGnBanksBanksWeeklyBalance(models.AbstractModel):
    _name = 'report.gn_banks_balance.report_banks_weekly_balance'
    _description = 'Informe HTML (QWeb) balance semanal bancarios por mes'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['banks.weekly.balance.report'].browse(docids)
        docs.ensure_one()

        wizard = docs
        common = self.env['banks.weekly.balance.common']
        payload = common.build_legacy_payload(wizard)

        currency = wizard.company_id.currency_id

        def fmt_money(amount):
            return formatLang(
                self.env,
                amount,
                currency_obj=currency,
            )

        return {
            'doc_ids': docids,
            'doc_model': 'banks.weekly.balance.report',
            'docs': docs,
            **payload,
            'fmt_money': fmt_money,
        }
