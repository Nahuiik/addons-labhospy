# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from functools import reduce
import datetime 
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_is_zero
from datetime import datetime, date
import io
import base64
from pprint import pprint 

class PurcharseAnalysisXLSX(models.AbstractModel):
    _name = 'report.gn_report_account.supplier_account_xls.xlsx'
    _description = 'Supplier Account State Report XLS'
    _inherit = 'report.report_xlsx.abstract'
    
    def generate_xlsx_report(self, workbook, data, lines):
        company_name = self.env.user.company_id.name
        sheet = workbook.add_worksheet(_('Supplier Account State'))
        info = self.get_data(data.get('start_date'),data.get('end_date'))
        
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'text_wrap':True,'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format24 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 13)
        sheet.set_column(2, 2, 30)
        sheet.set_column(3, 3, 18)
        sheet.set_column(4, 4, 25)
        sheet.set_column(5, 5, 19)
        sheet.set_column(6, 6, 30)
        sheet.set_column(7, 7, 15)
        sheet.set_column(8, 8, 15)
        sheet.set_column(9, 9, 15)
        sheet.set_row(7,26)
        # buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
        # sheet.insert_image('B2', "any_name.png", {'image_data': buf_image, 'x_scale': 0.13965, 'y_scale': 0.14535,})
        sheet.merge_range('A3:I3', company_name, format11)
        sheet.merge_range('A4:I4', _('REPORT SUPPLIER ACCOUNT STATE'), format11)

        sheet.merge_range('A7:B7', _('Start Date: %s')%(self.change_format(data.get('start_date'))), format24)
        sheet.merge_range('C7:D7', _('End Date: %s')%(self.change_format(data.get('end_date'))), format24)
        sheet.merge_range('E7:F7', _('Print Date: %s')%(datetime.today().strftime('%Y-%m-%d')), format24)

        pos = 8
        num = 1
        sheet.write(pos, 0, _('No.'), format21)
        sheet.write(pos, 1, _('Date'), format21)
        sheet.write(pos, 2, _('Name Supplier'), format21)
        sheet.write(pos, 3, _('Invoice Supplier'), format21)
        sheet.write(pos, 4, _('Reference'), format21)
        sheet.write(pos, 5, _('Date Invoice'), format21)
        sheet.write(pos, 6, _('Movement Invoice'), format21)
        sheet.write(pos, 7, _('Debits'), format21)
        sheet.write(pos, 8, _('Credits'), format21)
        sheet.write(pos, 9, _('Balance'), format21)
        pos+=1
        balance=0
        for inv in info:
            balance+=-inv.get('debits')+inv.get('credits')
            sheet.write(pos,0, num,format25)
            sheet.write(pos,1, inv.get('date'),format22)
            sheet.write(pos,2, inv.get('name_supplier'),format22)
            sheet.write(pos,3, inv.get('number_invoice_supplier'),format22)
            sheet.write(pos,4, inv.get('ref'),format22)
            sheet.write(pos,5, inv.get('date_invoice'),format22)
            sheet.write(pos,6, inv.get('movement_invoice'),format22)
            sheet.write(pos,7, inv.get('debits'),format3)
            sheet.write(pos,8, inv.get('credits'),format3)
            sheet.write(pos,9, balance,format3)
            pos+=1
            num+=1

    def get_data(self, start_date, end_date):
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
        ]
        if start_date:
            domain.append(('invoice_date', '>=', start_date))
        if end_date:
            domain.append(('invoice_date', '<=', end_date))

        invoices = self.env['account.move'].search(domain, order='invoice_date,name')
        info = []
        for invoice in invoices:
            payments_data = []
            widget = invoice.sudo().invoice_payments_widget or {}
            if widget:
                payments_data = widget.get('content', [])

            debits = sum(payment.get('amount', 0.0) for payment in payments_data)
            date_payment_parts = [
                self.change_format(payment.get('date') or payment.get('payment_date'))
                for payment in payments_data
                if payment.get('date') or payment.get('payment_date')
            ]
            movement_parts = [
                payment.get('name') or payment.get('journal_name') or payment.get('ref') or ''
                for payment in payments_data
            ]

            residual = invoice.amount_residual
            if float_is_zero(residual, precision_rounding=invoice.currency_id.rounding):
                residual = 0.0

            sort_date = invoice.invoice_date or invoice.date or invoice.date
            info.append({
                'date': self.change_format(sort_date),
                'name_supplier': invoice.partner_id.name or '',
                'number_invoice_supplier': invoice.name or '',
                'ref': invoice.ref or 'N/A',
                'date_invoice': ' '.join(filter(None, date_payment_parts)) or self.change_format(invoice.invoice_date or invoice.date),
                'movement_invoice': ' '.join(filter(None, movement_parts)) or '-',
                'debits': debits,
                'credits': residual,
                'sort_key': sort_date or invoice.write_date,
            })

        return sorted(info, key=lambda item: item.get('sort_key') or datetime.min)

    def change_format(self, value):
        if not value:
            return ''
        if isinstance(value, datetime):
            return value.strftime('%d/%m/%Y')
        if isinstance(value, date):
            return value.strftime('%d/%m/%Y')
        if isinstance(value, str):
            for fmt in ('%Y-%m-%d', DEFAULT_SERVER_DATETIME_FORMAT, '%Y-%m-%d %H:%M:%S'):
                try:
                    parsed = datetime.strptime(value, fmt)
                    return parsed.strftime('%d/%m/%Y')
                except ValueError:
                    continue
            return value
        return str(value)
