# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ReportGnAccountingSales(models.AbstractModel):
    _name = 'report.gn_accounting_reports.report_sales_document'
    _description = 'Reporte de ventas QWeb'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gn.accounting.sales.report.wizard'].browse(docids)
        wizard.ensure_one()
        payload = wizard._build_report_data()
        ts = fields.Datetime.context_timestamp(wizard, fields.Datetime.now())
        return {
            'doc_ids': docids,
            'docs': wizard,
            'company': wizard.company_id,
            'report_title': _('Reporte de ventas'),
            'period_from': wizard.date_from.strftime('%d/%m/%Y') if wizard.date_from else '',
            'period_to': wizard.date_to.strftime('%d/%m/%Y') if wizard.date_to else '',
            'print_date': ts.strftime('%d/%m/%Y'),
            'print_time': ts.strftime('%H:%M:%S'),
            'fmt_qty': wizard._fmt_qty,
            'fmt_money': wizard._fmt_money,
            **payload,
        }
