# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime, date
import io
import base64

class custAccStatementXlsx(models.AbstractModel):
    _name = 'report.gn_report_account.cust_acc_statement_xls.xlsx'
    _description = 'Customer Account Statement XLS'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
        cont = 1
        company_name = self.env.user.company_id.name
        sheet = workbook.add_worksheet(_('Account Status'))
        info = self.get_data(data.get('start_date'), data.get('end_date'))

        cont+=1
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format23 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format24 = workbook.add_format({'font_size': 10, 'align': 'right', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format26 = workbook.add_format({'font_size': 10, 'align': 'right', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format27 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#000000','bg_color':'#ffff00'})
        format28 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True, 'bg_color':'#ffff00'})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00', 'bg_color':'#ffff00'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 35)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 3, 18)
        sheet.set_column(4, 4, 40)
        sheet.set_column(5, 5, 15)
        sheet.set_column(6, 6, 15)
        sheet.set_column(7, 7, 15)
        sheet.set_column(8, 8, 15)

        today = date.today()

        sheet.merge_range('B3:I3', company_name, format11)
        sheet.merge_range('B4:I4', _('Customer Account Status'), format11)
        sheet.merge_range('B5:C5', _('Printings Date: %s')%(today.strftime("%d/%m/%Y")), format23)
        sheet.merge_range('B6:C6', _('Start Date: %s')%(self.change_format(data.get('start_date'))), format23)
        sheet.merge_range('D6:E6', _('End Date: %s')%(self.change_format(data.get('end_date'))), format23)

        pos = 8
        sheet.write(7, 1, _('Customer Name'), format21)
        sheet.write(7, 2, _('Invoice'), format21)
        sheet.write(7, 3, _('Date Invoice'), format21)
        sheet.write(7, 4, _('Amount Invoice'), format21)
        sheet.write(7, 5, _('Payment'), format21)
        sheet.write(7, 6, _('Reference Payment'), format21)
        sheet.write(7, 7, _('Amount Payment'), format21)
        sheet.write(7, 8, _('Residual'), format21)
        sheet.write(7, 9, _('Date Payment'), format21)
        for inv in info:
            sheet.write(pos, 1, inv.get('customer') or '', format22)
            sheet.write(pos, 2, inv.get('name_invoice') or '', format22)
            sheet.write(pos, 3, inv.get('date_invoice') or '', format22)
            sheet.write_number(pos, 4, inv.get('amount_invoice') or 0, format3)
            sheet.write(pos, 5, inv.get('name_payment') or '', format22)
            sheet.write(pos, 6, inv.get('reference') or '', format22)
            sheet.write_number(pos, 7, inv.get('amount_payment') or 0, format3)
            sheet.write_number(pos, 8, inv.get('amount_invoice') - inv.get('amount_payment'), format3)
            sheet.write(pos, 9, inv.get('date_payment') or '', format22)
            # sheet.write_number(pos, 6, 0, format3)
            # sheet.write(pos, 8, inv.get('date') or '', format24)
            pos+=1
            # if inv.get('payments'):
            #     for pay in inv.get('payments'):
            #         sheet.write(pos, 1, pay.get('patient') or '', format22)
            #         sheet.write(pos, 2, pay.get('type') or '', format22)
            #         sheet.write(pos, 3, pay.get('number') or '', format22)
            #         sheet.write(pos, 4, pay.get('reference') or '', format22)
            #         sheet.write_number(pos, 5, 0, format3)
            #         sheet.write_number(pos, 6, pay.get('credit') or 0, format3)
            #         sheet.write_number(pos, 7, 0, format3)
            #         sheet.write(pos, 8, pay.get('date') or '', format24)
            #         pos+=1

    def get_data(self, start_date, end_date):
        info = []
        info = []
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ]
        if start_date:
            domain.append(('invoice_date', '>=', start_date))
        if end_date:
            domain.append(('invoice_date', '<=', end_date))

        invoices = self.env['account.move'].search(domain, order='invoice_date, name')
        for invoice in invoices:
            payments_vals = invoice.sudo().invoice_payments_widget and invoice.sudo().invoice_payments_widget.get('content', []) or []
            if payments_vals:
                for payment in payments_vals:
                    info.append({
                        'customer': invoice.partner_id.name or '',
                        'name_invoice': invoice.name or '',
                        'date_invoice': self.change_format(invoice.invoice_date),
                        'amount_invoice': invoice.amount_total,
                        'pay_state': invoice.payment_state,
                        'reference': payment.get('ref') or '',
                        'name_payment': payment.get('journal_name') or '',
                        'amount_payment': payment.get('amount') or 0.0,
                        'date_payment': self.change_format(payment.get('date')),
                    })
            else:
                info.append({
                    'customer': invoice.partner_id.name or '',
                    'name_invoice': invoice.name or '',
                    'date_invoice': self.change_format(invoice.invoice_date),
                    'amount_invoice': invoice.amount_total,
                    'pay_state': invoice.payment_state,
                    'reference': '',
                    'name_payment': '',
                    'amount_payment': 0.0,
                    'date_payment': '',
                })
        info_sorted = sorted(info, key=lambda inv: inv.get('date_invoice'))
        return info_sorted

    def change_format(self, value):
        if not value:
            return ''
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.strftime('%d/%m/%Y')
        if isinstance(value, str):
            try:
                parsed = datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                return value
            return parsed.strftime('%d/%m/%Y')
        return str(value)
