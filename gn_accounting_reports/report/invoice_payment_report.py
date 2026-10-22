# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ReportGnAccountingInvoicePayment(models.AbstractModel):
    _name = 'report.gn_accounting_reports.report_invoice_payment_document'
    _description = 'Reporte premium facturas y pagos QWeb'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gn.accounting.invoice.payment.report.wizard'].browse(docids)
        wizard.ensure_one()
        payload = wizard._build_report_data()
        ts = fields.Datetime.context_timestamp(wizard, fields.Datetime.now())
        return {
            'doc_ids': docids,
            'docs': wizard,
            'company': wizard.company_id,
            'report_title': _('Reporte premium facturas y pagos'),
            'period_from': wizard._fmt_date(wizard.date_from),
            'period_to': wizard._fmt_date(wizard.date_to),
            'invoice_period_from': wizard._fmt_date(wizard.invoice_date_from),
            'invoice_period_to': wizard._fmt_date(wizard.invoice_date_to),
            'print_date': ts.strftime('%d/%m/%Y'),
            'print_time': ts.strftime('%H:%M:%S'),
            'fmt_qty': wizard._fmt_qty,
            'fmt_money': wizard._fmt_money,
            **payload,
        }


class ReportGnAccountingInvoicePaymentHtml(models.AbstractModel):
    _name = 'report.gn_accounting_reports.report_invoice_payment_html'
    _inherit = 'report.gn_accounting_reports.report_invoice_payment_document'
    _description = 'Reporte premium facturas y pagos QWeb (HTML)'
