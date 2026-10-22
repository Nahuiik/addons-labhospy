# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ReportPartnerAgeing(models.AbstractModel):
    _name = "report.bi_financial_reports_comm.partner_ageing_pdf_report"
    _description = "Partner Ageing PDF Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["partner.ageing"].browse(docids)
        data = data or {}
        if docs:
            record = docs[0]
            context = {
                "on_date": record.on_date,
                "period_length": record.period_length,
                "account_type": record.account_type,
                "account_ids": record.account_ids.ids,
                "partner_ids": record.partner_ids.ids,
                "partner_tag_ids": record.partner_tag_ids.ids,
                "based_on": record.based_on,
            }
            report_data = self.env["partner.ageing"].with_context(context).get_data_ageing_report()
        elif data.get("receivable") is not None or data.get("payable") is not None:
            report_data = {
                "receivable": data.get("receivable", {"partners": [], "period_total": {}, "section_label": "Vencidas por cobrar"}),
                "payable": data.get("payable", {"partners": [], "period_total": {}, "section_label": "Vencidas por pagar"}),
                "periods": data.get("periods", {}),
                "currency_data": data.get("currency_data", {"symbol": "$"}),
                "expandedPartners": data.get("expandedPartners", {}),
            }
        else:
            report_data = {
                "receivable": {"partners": [], "period_total": {}, "section_label": "Vencidas por cobrar"},
                "payable": {"partners": [], "period_total": {}, "section_label": "Vencidas por pagar"},
                "periods": {},
                "currency_data": {"symbol": "$"},
            }
        return {
            "doc_ids": docids,
            "doc_model": "partner.ageing",
            "docs": docs,
            "data": data,
            **report_data,
        }
