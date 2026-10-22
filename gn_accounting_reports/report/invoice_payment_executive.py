# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models, _


class ReportInvoicePaymentExecutive(models.AbstractModel):
    _name = 'report.gn_accounting_reports.report_invoice_payment_executive'
    _description = 'Reporte ejecutivo facturas y pagos'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gn.accounting.invoice.payment.executive.wizard'].browse(docids)
        wizard.ensure_one()
        if not wizard.dashboard_json:
            wizard.prepare_from_filters(json.loads(wizard.filter_json or '{}'))
        payload = json.loads(wizard.dashboard_json or '{}')
        ts = fields.Datetime.context_timestamp(wizard, fields.Datetime.now())
        company = wizard.company_id
        fmt = lambda v: format(v, ',.2f') if isinstance(v, (int, float)) else v
        fmt_pct = lambda v: '%.1f' % (float(v or 0))
        return {
            'doc_ids': docids,
            'docs': wizard,
            'company': company,
            'report_title': _('Facturas y pagos — Informe ejecutivo'),
            'payload': payload,
            'header': payload.get('header', {}),
            'kpis': payload.get('kpis', {}),
            'insights': payload.get('insights', []),
            'aging': payload.get('aging', {}),
            'charts': payload.get('charts', {}),
            'filters': payload.get('filters_applied', {}),
            'currency_symbol': company.currency_id.symbol,
            'print_date': ts.strftime('%d/%m/%Y'),
            'print_time': ts.strftime('%H:%M:%S'),
            'fmt_money': fmt,
            'fmt_pct': fmt_pct,
        }
