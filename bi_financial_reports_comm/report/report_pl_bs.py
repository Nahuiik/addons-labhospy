# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.tools.misc import format_amount


def _sum_accounts_in_sections(struct, *section_keys):
    total = 0.0
    for key in section_keys:
        section = struct.get(key) or {}
        for acc in section.get("accounts") or []:
            total += float(acc.get("balance") or 0)
    return total


class ReportProfitLossPdf(models.AbstractModel):
    _name = "report.bi_financial_reports_comm.profit_loss_pdf_report"
    _description = "Estado de Resultados PDF Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        currency = self.env.company.currency_id

        def format_currency(amount):
            try:
                val = float(amount if amount is not None else 0.0)
            except (TypeError, ValueError):
                val = 0.0
            return format_amount(self.env, val, currency)

        profit_loss_data = data.get("ProfitLossData")
        if not profit_loss_data and docids:
            profit_loss_data = (
                self.env["profit.loss.report"].browse(docids[:1]).get_data_profit_loss()
            )
        profit_loss_data = profit_loss_data or {}

        inc = profit_loss_data.get("income", {}) or {}
        exp = profit_loss_data.get("expense", {}) or {}
        tr = float((inc.get("income") or {}).get("total") or 0)
        cod = float((exp.get("expense_direct_cost") or {}).get("total") or 0)
        toe = float((exp.get("expense") or {}).get("total") or 0)
        tio = float((inc.get("income_other") or {}).get("total") or 0)
        ted = float((exp.get("expense_depreciation") or {}).get("total") or 0)

        gross = data.get("grossProfitTotal")
        operating = data.get("operatingIncomeTotal")
        net = data.get("netProfitTotal")
        if gross is None:
            gross = tr - cod
        if operating is None:
            operating = gross - toe
        if net is None:
            net = operating + tio - ted

        return {
            "doc_ids": docids,
            "doc_model": "profit.loss.report",
            "docs": self.env["profit.loss.report"].browse(docids),
            "ProfitLossData": profit_loss_data,
            "expandedType": data.get("expandedType") or {},
            "grossProfitTotal": gross,
            "operatingIncomeTotal": operating,
            "netProfitTotal": net,
            "format_currency": format_currency,
        }


class ReportBalanceSheetPdf(models.AbstractModel):
    _name = "report.bi_financial_reports_comm.balance_sheet_pdf_report"
    _description = "Balance Sheet PDF Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        currency = self.env.company.currency_id

        def format_currency(amount):
            try:
                val = float(amount if amount is not None else 0.0)
            except (TypeError, ValueError):
                val = 0.0
            return format_amount(self.env, val, currency)

        balance_sheet_data = data.get("balanceSheetData")
        if not balance_sheet_data and docids:
            balance_sheet_data = (
                self.env["balance.sheet.report"].browse(docids[:1]).get_data_balance_sheet()
            )
        balance_sheet_data = balance_sheet_data or {}

        assets = balance_sheet_data.get("assets") or {}
        liabilities = balance_sheet_data.get("liabilities") or {}

        current_assets_total = data.get("currentAssetsTotal")
        if current_assets_total is None:
            current_assets_total = _sum_accounts_in_sections(
                assets, "bank_cash", "receivables", "current_assets", "prepayments"
            )

        current_liabilities_total = data.get("currentLiabilitiesTotal")
        if current_liabilities_total is None:
            current_liabilities_total = _sum_accounts_in_sections(
                liabilities, "current_liabilities", "payables", "credit_card"
            )

        totals = data.get("totals")
        if totals is None:
            totals = balance_sheet_data.get("totals") or {}

        return {
            "doc_ids": docids,
            "doc_model": "balance.sheet.report",
            "docs": self.env["balance.sheet.report"].browse(docids),
            "balanceSheetData": balance_sheet_data,
            "currency": data.get("currency") or balance_sheet_data.get("currency_data", {}),
            "expandedType": data.get("expandedType") or {},
            "totals": totals,
            "currentAssetsTotal": current_assets_total,
            "currentLiabilitiesTotal": current_liabilities_total,
            "AssetsTotalBalance": data.get("AssetsTotalBalance"),
            "formatCurrency": format_currency,
        }
