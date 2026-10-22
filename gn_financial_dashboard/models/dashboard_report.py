# -*- coding: utf-8 -*-
"""Modelo de soporte para el reporte ejecutivo PDF (QWeb).

El reporte no opera sobre registros: recibe los filtros activos del tablero en
``data`` y reutiliza ``gn.financial.dashboard.get_dashboard_data`` para construir
el payload, garantizando que el PDF muestre exactamente lo mismo que la pantalla.
"""
from odoo import api, models


class FinancialExecutiveReport(models.AbstractModel):
    _name = 'report.gn_financial_dashboard.report_executive_document'
    _description = 'Reporte ejecutivo financiero'

    @api.model
    def _get_report_values(self, docids, data=None):
        filters = (data or {}).get('filters') or {}
        dashboard = self.env['gn.financial.dashboard']
        payload = dashboard.get_dashboard_data(filters)
        # Etiquetas de fecha formateadas (dd/mm/yyyy) y números con
        # coma como separador de miles, listos para ser inyectados en el
        # template QWeb sin lógica adicional.
        period = payload.get('period') or {}
        payload['period_label'] = {
            'date_from': self._fmt_iso_date(period.get('date_from')),
            'date_to': self._fmt_iso_date(period.get('date_to')),
        }
        payload['kpis_fmt'] = self._fmt_kpis(payload.get('kpis') or {})
        # También formateamos aging para consistencia visual.
        for aging_key in ('receivable', 'payable'):
            block = (payload.get('aging') or {}).get(aging_key) or {}
            if 'values' in block:
                block['values_fmt'] = [self._fmt_money(v) for v in block['values']]
        for it in (payload.get('expense_ranking', {}) or {}).get('items', []):
            if 'amount' in it:
                it['amount_fmt'] = self._fmt_money(it['amount'])
        return {
            'doc_ids': docids,
            'doc_model': 'gn.financial.dashboard',
            'docs': [],
            'data': data,
            'd': payload,
            'company': self.env.company,
            'currency': payload.get('currency', {}),
        }

    @staticmethod
    def _fmt_iso_date(iso):
        """Convierte 'YYYY-MM-DD' a 'DD/MM/YYYY'. Tolerante a None/format."""
        if not iso:
            return ''
        parts = str(iso)[:10].split('-')
        if len(parts) == 3:
            return '%s/%s/%s' % (parts[2], parts[1], parts[0])
        return str(iso)

    @staticmethod
    def _fmt_money(value, decimals=2):
        """Formato con coma como separador de miles, punto decimal."""
        try:
            return ('{:,.%df}' % decimals).format(float(value or 0.0))
        except (ValueError, TypeError):
            return str(value)

    @classmethod
    def _fmt_kpis(cls, kpis):
        # Lista de KPIs con su número de decimales preferido.
        money_keys = (
            'revenue', 'cogs', 'gross_profit', 'expenses', 'net_profit',
            'receivables', 'payables', 'closing_bank', 'working_capital',
            'ebit', 'ebitda', 'current_assets', 'current_liab', 'quick_assets',
            'total_assets', 'total_liab', 'equity',
        )
        pct_keys = (
            'net_margin', 'gross_margin', 'operating_margin', 'ebitda_margin',
            'roa', 'roe',
        )
        out = {}
        for k, v in (kpis or {}).items():
            if k in money_keys:
                out[k] = cls._fmt_money(v, 2)
            elif k in pct_keys:
                out[k] = cls._fmt_money(v, 1)
            else:
                out[k] = cls._fmt_money(v, 2)
        return out
