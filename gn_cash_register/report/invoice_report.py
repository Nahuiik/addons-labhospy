import time
from odoo import api, models
from dateutil.parser import parse
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from collections import defaultdict


class ReportInvoices(models.AbstractModel):
    _name = 'report.gn_cash_register.invoice_outstanding'

    @api.model
    def get_report_values(self, docids, data=None):
        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        start_time = datetime.strptime(docs.start_date, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S')
        end_time = datetime.strptime(docs.end_date, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S')
        start_date_adjusted = datetime.strptime(docs.start_date, '%Y-%m-%d %H:%M:%S') - timedelta(hours=6)
        end_date_adjusted = datetime.strptime(docs.end_date, '%Y-%m-%d %H:%M:%S') - timedelta(hours=6)
        start_times = (datetime.strptime(docs.start_date, '%Y-%m-%d %H:%M:%S') - timedelta(hours=0)).strftime('%Y-%m-%d %H:%M:%S')
        end_times = (datetime.strptime(docs.end_date, '%Y-%m-%d %H:%M:%S') - timedelta(hours=0)).strftime('%Y-%m-%d %H:%M:%S')

        invoices = self.env['account.payment'].search([
            ('payment_date', '>=', start_date_adjusted),
            ('payment_date', '<=', end_date_adjusted),
            ('create_date', '>=', start_times),
            ('create_date', '<=', end_times),
            ('create_uid', '=', docs.partner_id.id),
            ('state', '=', 'posted')
        ])
        credit = self.env['account.invoice'].search([
                ('date_invoice', '>=', docs.start_date),
                ('date_invoice', '<=', docs.end_date),
                ('user_id', '=', docs.partner_id.id),
                ('type', '=', 'out_invoice'),
                ('state', '=', 'open')
            ])
        
        journal_summary = {}
        invoice_lines_summary = []

        for invoice in invoices:
            journal_name = invoice.journal_id.name
            amount = invoice.amount

            invoice_lines = invoice.invoice_lines
            lines_data = [{
                'move_name': line.invoice_id.move_name,
                'date_invoice': f"{datetime.strptime(line.invoice_id.date_invoice, '%Y-%m-%d').strftime('%d/%m/%Y')} {line.invoice_id.create_time}" if line.invoice_id.date_invoice and line.invoice_id.create_time else '',
                'subtotal': line.allocation,
                'journal_id': line.payment_id.journal_id.name,
                'payment_name': line.payment_id.name,
                'payment_date': datetime.strptime(line.payment_id.payment_date, '%Y-%m-%d').strftime('%d/%m/%Y') ,
                'payment_amount': line.payment_id.amount,
                'communication': line.payment_id.communication,
                'payment_id': line.payment_id.id,
            } for line in invoice_lines]

            if not invoice_lines:
                lines_data = [{
                    'move_name': invoice.move_name,
                    'date_invoice': f"{datetime.strptime(line.date_invoice, '%Y-%m-%d').strftime('%d/%m/%Y')} {line.create_time}" if line.date_invoice and line.create_time else '',
                    'subtotal': sum(p.amount for p in line.payment_ids if p.id == invoice.id),
                    'journal_id': invoice.name,
                    'payment_name': invoice.name,
                    'payment_date': datetime.strptime(invoice.payment_date, '%Y-%m-%d').strftime('%d/%m/%Y') ,
                    'payment_amount': invoice.amount,
                    'communication': invoice.communication,
                    'payment_id': invoice.id,
                } for line in invoice.invoice_ids]

            invoice_lines_summary.extend(lines_data)

            if journal_name in journal_summary:
                journal_summary[journal_name] += amount
            else:
                journal_summary[journal_name] = amount

        invoice_lines_summary = sorted(invoice_lines_summary, key=lambda x: x['move_name'], reverse=True)

        docs.e_date = end_date_adjusted.strftime('%d de %B de %Y %H:%M')
        docs.s_date = start_date_adjusted.strftime('%d de %B de %Y %H:%M')
        result = {
            'docs': docs,
            'invoices': invoices,
            'credit': credit,
            'invoice_lines_summary': invoice_lines_summary,
            'journal_summary': [
                {
                    'journal_name': journal_name,
                    'total_amount': journal_summary[journal_name]
                }
                for journal_name in journal_summary
            ]
        }

        return result