# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import io
import base64
from datetime import datetime

class purchasePaymentsXls(models.AbstractModel):
    _name = 'report.gn_report_account.purchase_payment_report_xls.xlsx'
    _description = 'Purchase Payments Report XLS'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
        payments = self.get_payments(data.get('date_from'),data.get('date_to'))
        
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#20964F'})
        format23 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#000000','font_color': 'white'})
        format24 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': True, 'bold': False})
        format26 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': False})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'right','left':True,'right':True,'bottom': True, 'top': True, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet = workbook.add_worksheet(_('Payments'))
        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 15)
        sheet.set_column(2, 2, 25)
        sheet.set_column(3, 3, 30)
        sheet.set_column(4, 4, 60)
        sheet.set_column(5, 5, 25)
        sheet.set_column(6, 6, 25)
        sheet.set_column(7, 7, 15)

        sheet.merge_range('A4:F4', self.env.user.company_id.name, format1)
        sheet.merge_range('A5:F5', _('Purchase Payments Report').upper(), format11)
        
        sheet.write(6, 1, _('From : %s')%(self.change_format(data.get('date_from'))), format22)
        sheet.write(6, 2, _('To : %s')%(self.change_format(data.get('date_to'))), format22)

        pos = 9
        total = 0
        num = 1
        sheet.write(8, 0, '#', format21)
        sheet.write(8, 1, _('Pay Date'), format21)
        sheet.write(8, 2, _('Pay Number'), format21)
        sheet.write(8, 3, _('Journal Pay'), format21)
        sheet.write(8, 4, _('Reference'), format21)
        sheet.write(8, 5, _('Total'), format21)

        for payment in payments.get('info'):
            sheet.write(pos, 0, num, format21)
            sheet.write(pos, 1, payment.get('date'), format22)
            sheet.write(pos, 2, payment.get('number'), format22)
            sheet.write(pos, 3, payment.get('journal'), format22)
            sheet.write(pos, 4, payment.get('partner'), format22)
            sheet.write_number(pos, 5, payment.get('total'), format3)
            total+=payment.get('total')
            pos+=1
            num+=1

        sheet.write_number(pos, 5, total, format4)
        pos+=3
        for jour in payments.get('journals'):
            sheet.write(pos, 2, jour.get('journal'), format23)
            sheet.write_number(pos, 3, jour.get('total'), format5)
            pos+=1

    def get_payments(self,date_from,date_to):
        account_payment = self.env['account.payment']
        domain_payment = [('state','=','posted'),('payment_type','=','outbound')]
        info_payments = []
        if date_from:
            domain_payment.append(('date','>=',date_from))
        if date_to:
            domain_payment.append(('date','<=',date_to))

        obj_payment = account_payment.search(domain_payment)
        journal_ids = []
        journal_array = []
        for pay in obj_payment:
            info_payments.append({
                'date': self.change_format(pay.date),
                'number': pay.name,
                'total': pay.amount,
                'journal': pay.journal_id.name,
                'comercial': pay.create_uid.name,
                'partner': pay.ref or '',
                'state': self.get_state(pay.state)
            })
            #for journal in journal_pay:
            if pay.journal_id.id in journal_ids:
                journal_array[journal_ids.index(pay.journal_id.id)]['total']+=pay.amount
            else:
                journal_ids.append(pay.journal_id.id)
                journal_array.append({
                    'journal':pay.journal_id.name,
                    'total':pay.amount,
                })
        vals = {
            'info':info_payments,
            'journals':journal_array,
        }
        return vals

    def get_state(self,state):
        if state == 'draft':
            return _('Draft')
        elif state == 'posted':
            return _('Validated')
        elif state == 'reconciled':
            return _('Reconciled')
        elif state == 'cancelled':
            return _('Cancelled')

    def change_format(self,date):
        if date:
            date1 = datetime.strptime(str(date), '%Y-%m-%d')
            return date1.strftime('%d/%m/%Y')
    
