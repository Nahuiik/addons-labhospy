# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import io
import base64
from datetime import datetime

class salePaymentsXls(models.AbstractModel):
    _name = 'report.gn_report_account.sale_payment_report_xls.xlsx'
    _description = 'Sale Payments Report XLS'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
        payments = self.get_payments(data.get('date_from'),data.get('date_to'))
        
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format22a = workbook.add_format({'font_size': 10, 'align': 'left', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#000000','font_color': 'white'})
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

        sheet.merge_range('A4:G4', self.env.user.company_id.name, format1)
        sheet.merge_range('A5:G5', _('Sale Payments Reports').upper(), format11)
        
        sheet.write(6, 1, _('From : %s')%(self.change_format(data.get('date_from'))), format22)
        sheet.write(6, 2, _('To : %s')%(self.change_format(data.get('date_to'))), format22)

        pos = 9
        total = 0
        num = 1
        sheet.write(8, 0, '#', format21)
        sheet.write(8, 1, _('Pay Date'), format21)
        sheet.write(8, 2, _('Pay Number'), format21)
        sheet.write(8, 3, _('Journal Pay'), format21)
        sheet.write(8, 4, _('Invoices'), format21)
        sheet.write(8, 5, _('Total'), format21)

        for payment in payments.get('info'):
            sheet.write(pos, 0, num, format21)
            sheet.write(pos, 1, payment.get('date'), format22)
            sheet.write(pos, 2, payment.get('number'), format22)
            sheet.write(pos, 3, payment.get('journal'), format22)
            sheet.write(pos, 4, payment.get('invoices'), format22)
            sheet.write_number(pos, 5, payment.get('total'), format3)
            total+=payment.get('total')
            pos+=1
            num+=1

        sheet.write(pos, 4, _('Totals'), format21)
        sheet.write_number(pos, 5, total, format4)
        pos+=3
        sheet_journal = workbook.add_worksheet(_('Journal Pay'))
        sheet_journal.merge_range('A4:G4', self.env.user.company_id.name, format1)
        sheet_journal.merge_range('A5:G5', _('Sale Payments Reports').upper(), format11)
        sheet_journal.set_column(0, 0, 5)
        sheet_journal.set_column(1, 1, 30)
        sheet_journal.set_column(2, 2, 15)
        sheet_journal.write(8, 0, _('#'), format21)
        sheet_journal.write(8, 1, _('Diario'), format21)
        sheet_journal.write(8, 2, _('Total'), format21)
        pos=9
        num = 1
        for jour in payments.get('journals'):
            sheet_journal.write(pos, 0, num, format21)
            sheet_journal.write(pos, 1, jour.get('journal'), format22a)
            sheet_journal.write_number(pos, 2, jour.get('total'), format5)
            pos+=1
            num+=1

    def get_payments(self,date_from,date_to):
        account_payment = self.env['account.payment']
        domain_payment = [('state','=','posted'),('payment_type','=','inbound')]
        info_payments = []
        if date_from:
            domain_payment.append(('date','>=',date_from))
        if date_to:
            domain_payment.append(('date','<=',date_to))
            

        obj_payment = account_payment.search(domain_payment)
        journal_ids = []
        journal_array = []
        invoice_types = ('out_invoice', 'out_refund')
        for pay in obj_payment:
            invoice_moves = self._get_payment_invoices(pay, invoice_types)
            invoice_names = [name for name in invoice_moves.mapped('name') if name]
            if not invoice_names:
                invoice_names = [ref for ref in invoice_moves.mapped('payment_reference') if ref] or [ref for ref in invoice_moves.mapped('ref') if ref]
            invoices = ', '.join(invoice_names) or (pay.ref or '')
            info_payments.append({
                'date': self.change_format(pay.date),
                'number': pay.name,
                'total': pay.amount,
                'journal': pay.journal_id.name,
                'comercial': pay.create_uid.name,
                'invoices': invoices,
                'state': self.get_state(pay.state)
            })

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

    def _get_payment_invoices(self, payment, invoice_types):
        move = payment.move_id if hasattr(payment, 'move_id') and payment.move_id else payment
        matched = move.line_ids.mapped('matched_debit_ids.move_id') | move.line_ids.mapped('matched_credit_ids.move_id')
        matched |= payment.reconciled_invoice_ids
        return matched.filtered(lambda m: m.move_type in invoice_types)

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
