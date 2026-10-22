# -*- coding: utf-8 -*-
from odoo import api, models


class BlindClosingVoucherReport(models.AbstractModel):
    _name = "report.gn_daily_cash_closing.blind_closing_voucher"
    _description = "Voucher Cierre Inicial a Ciegas"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env["gn.cash.closing.blind.wizard"].browse(docids)
        if not wizards:
            return {"docs": [], "company": self.env.company}
        wiz = wizards[0]
        def _fmt(v):
            return "{:,.2f}".format(v) if v is not None else "0.00"

        return {
            "docs": wizards,
            "doc_ids": docids,
            "doc_model": "gn.cash.closing.blind.wizard",
            "company": self.env.company,
            "user_name": wiz.user_id.name if wiz.user_id else "",
            "date": str(wiz.date) if wiz.date else "",
            "branch_name": wiz.branch_id.name if wiz.branch_id else "",
            "efectivo_digitado": wiz.efectivo_digitado or 0,
            "efectivo_calculado": wiz.efectivo_calculado or 0,
            "efectivo_diferencia": wiz.efectivo_diferencia or 0,
            "tarjetas_digitado": wiz.tarjetas_digitado or 0,
            "tarjetas_calculado": wiz.tarjetas_calculado or 0,
            "tarjetas_diferencia": wiz.tarjetas_diferencia or 0,
            "transferencias_digitado": wiz.transferencias_digitado or 0,
            "transferencias_calculado": wiz.transferencias_calculado or 0,
            "transferencias_diferencia": wiz.transferencias_diferencia or 0,
            "efectivo_digitado_fmt": _fmt(wiz.efectivo_digitado),
            "efectivo_calculado_fmt": _fmt(wiz.efectivo_calculado),
            "efectivo_diferencia_fmt": _fmt(wiz.efectivo_diferencia),
            "tarjetas_digitado_fmt": _fmt(wiz.tarjetas_digitado),
            "tarjetas_calculado_fmt": _fmt(wiz.tarjetas_calculado),
            "tarjetas_diferencia_fmt": _fmt(wiz.tarjetas_diferencia),
            "transferencias_digitado_fmt": _fmt(wiz.transferencias_digitado),
            "transferencias_calculado_fmt": _fmt(wiz.transferencias_calculado),
            "transferencias_diferencia_fmt": _fmt(wiz.transferencias_diferencia),
        }
