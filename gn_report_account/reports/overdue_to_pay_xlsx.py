# -*- coding: utf-8 -*-
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
from odoo import models, api, fields, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io
import base64

class ReportOverdueToPayXlsx(models.AbstractModel):
    _name = "report.a_f_r.report_overdue_to_pay_xlsx"
    _description = "Overdue To Pay Report XLS"
    _inherit = "report.report_xlsx.abstract"


    def generate_xlsx_report(self, workbook, data,objeives):
        cont = 1
        company_name = self.env.user.company_id.name
        sheet = workbook.add_worksheet(_('Payment Supplier'))
        account = self.get_data(data.get('start_date'),data.get('end_date'))
        buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
        # sheet.insert_image('A1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.8, 'y_scale': 0.9,})

        cont+=1
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#000000'})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format23 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': True, 'top': False, 'bold': True})
        format23a = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#000000'})
        format24 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#FFFFFF','bg_color':'#000000'})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'center', 'left':False,'right':False,'bottom': False, 'top': False, 'bold':False ,'font_size': 10,'num_format': 'L '+'#,##0.00'})
        format5a = workbook.add_format({'align':'right', 'left':False,'right':False,'bottom': True, 'top': False, 'bold':True ,'font_size': 10,'num_format': 'L '+'#,##0.00'})
        format5b = workbook.add_format({'align':'right', 'left':True,'right':True,'bottom': True, 'top': True, 'bold':True ,'font_size': 10,'num_format': 'L '+'#,##0.00', 'font_color':'#ffffff','bg_color':'#000000'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 25)
        sheet.set_column(3, 3, 15)
        sheet.set_column(4, 4, 15)
        sheet.set_column(5, 5, 18)
        sheet.set_column(6, 12, 12)
        sheet.set_column(13, 13, 15)

        sheet.merge_range('B3:F3', company_name, format11)
        sheet.merge_range('B4:F4', _('Reports Payment Supplier'), format11)
        if data.get('start_date'):
            sheet.merge_range('B6:C6', _('Start Date: %s')%(data.get('start_date')), format24)
        if data.get('end_date'):
            sheet.merge_range('D6:E6', _('End Date: %s')%(data.get('end_date')), format24)

        pos = 8
        num = 1
        total = 0
        sheet.write(7, 0, _('No.'), format21)
        sheet.write(7, 1, _('Invoice'), format21)
        sheet.write(7, 2, _('Numero de Cuenta'), format21)
        sheet.write(7, 3, _('Invoice Date'), format21)
        sheet.write(7, 4, _('Invoice Date Due'), format21)
        sheet.write(7, 5, _('Suma de Días Mora'), format21)
        sheet.write(7, 6, _('Retención 1%'), format21)
        sheet.write(7, 7, _('Retención 12.5%'), format21)
        sheet.write(7, 8, _('SUM 1-30 Días'), format21)
        sheet.write(7, 9, _('SUM 31-60 Días'), format21)
        sheet.write(7, 10, _('SUM 61-90 Días'), format21)
        sheet.write(7, 11, _('SUM Más 90 Días'), format21)
        sheet.write(7, 12, _('SUMA de Saldos'), format21)
        sheet.write(7, 13, _('Saldos - Retenciones'), format21)
        sub_total=total=pos_supplier=t_term_time_0_30=t_term_time_31_60=t_term_time_61_90=t_term_time_90=0
        for move in account:
            pos_supplier=pos
            sheet.write(pos, 0, num, format23)
            sheet.merge_range('B'+str(pos+1)+':E'+str(pos+1), move.get('name_supplier'), format23)
            sheet.write(pos, 12, move.get('amount'), format5a)
            sheet.write(pos, 13, move.get('amount') - move.get('t_retention_1') - move.get('t_retention_12_5'), format5a)
            sub_total+=move.get('amount')
            total += move.get('amount') - move.get('t_retention_1') - move.get('t_retention_12_5')
            pos+=1
            num2=1
            sheet.write(pos_supplier, 5, _(''), format23)
            sheet.write(pos_supplier, 6, move.get('t_retention_1'), format5a)
            sheet.write(pos_supplier, 7, move.get('t_retention_12_5'), format5a)
            sheet.write(pos_supplier, 8, move.get('term_time_0_30'), format5a)
            t_term_time_0_30+=move.get('term_time_0_30')
            sheet.write(pos_supplier, 9, move.get('term_time_31_60'), format5a)
            t_term_time_31_60+=move.get('term_time_31_60')
            sheet.write(pos_supplier, 10, move.get('term_time_61_90'), format5a)
            t_term_time_61_90+=move.get('term_time_61_90')
            sheet.write(pos_supplier, 11, move.get('term_time_90'), format5a)
            t_term_time_90+=move.get('term_time_90')
            for line in move.get('value'):
                sheet.write(pos, 0, str(num)+'-'+str(num2), format22)
                sheet.write(pos, 1, line.get('invoice'), format22)
                sheet.write(pos, 2, move.get('bank_number'), format22)
                sheet.write(pos, 3, line.get('invoice_date'), format22)
                sheet.write(pos, 4, line.get('invoice_due'), format22)
                sheet.write(pos, 6, line.get('retention_1'), format22)
                sheet.write(pos, 7, line.get('retention_12_5'), format22)
                sheet.write(pos, 8, 0.00, format5)
                sheet.write(pos, 9, 0.00, format5)
                sheet.write(pos, 10, 0.00, format5)
                sheet.write(pos, 11, 0.00, format5)
                if line.get('deu_time')>0:
                    sheet.write(pos, 5, line.get('deu_time'), format22)
                else:
                    sheet.write(pos, 5, 0, format22)
                if line.get('deu_time') >=0 and line.get('deu_time')<=30:
                    sheet.write(pos, 8, line.get('amount'), format5)
                elif line.get('deu_time') >=31 and line.get('deu_time')<=60:
                    sheet.write(pos, 9, line.get('amount'), format5)
                elif line.get('deu_time') >=61 and line.get('deu_time')<=90:
                    sheet.write(pos, 10, line.get('amount'), format5)
                elif line.get('deu_time') >90:
                    sheet.write(pos, 11, line.get('amount'), format5)
                pos+=1
                num2+=1
            if len(move.get('value'))==0:
                pos+=1
            num+=1
        pos+=1
        sheet.merge_range('A'+str(pos+1)+':F'+str(pos+1), _('Total'), format23a)
        sheet.write(pos, 6, _(''), format5b)
        sheet.write(pos, 7, _(''), format5b)
        sheet.write(pos, 8, t_term_time_0_30, format5b)
        sheet.write(pos, 9, t_term_time_31_60, format5b)
        sheet.write(pos, 10, t_term_time_61_90, format5b)
        sheet.write(pos, 11, t_term_time_90, format5b)
        sheet.write(pos, 12, sub_total, format5b)
        sheet.write(pos, 13, total, format5b)
    def get_data(self, start_date, end_date):
        domain = [('move_type','=','in_invoice'),('state','=','posted'),('payment_state','in',['partial','not_paid'])]
        if start_date:
            domain.append(('date','>=',start_date))
        if end_date:
            domain.append(('date','<=',end_date))
        account = self.env['account.move'].search(domain)
        info = []
        name_partner=[]
        name_partner_value=[]
        for move in account.sorted(key=lambda r: r.partner_id.name):
            if move.partner_id.name in name_partner:
                for inf in info:
                    if inf['name_supplier']==move.partner_id.name:
                        term_time_0_30=term_time_31_60=term_time_61_90=term_time_90=0
                        deu_time, term_time = self.calculate_time_date(move.invoice_date,move.invoice_date_due)
                        retention_1=retention_12_5=0
                        retention_1 = getattr(move, 'ret_amount_1', 0.0)
                        retention_12_5 = getattr(move, 'ret_amount_12_5', 0.0)
                        inf['value'].append({
                            'invoice':move.supplier_invoice_number,
                            'invoice_date':self.change_format(move.invoice_date),
                            'invoice_due':self.change_format(move.invoice_date_due),
                            'amount': move.amount_residual,
                            'journal': move.journal_id.name,
                            'deu_time':deu_time, 
                            'term_time':term_time,
                            'debt_days':deu_time-term_time,
                            'retention_1':retention_1,
                            'retention_12_5':retention_12_5,
                        })
                        if deu_time >=0 and deu_time<=30:
                            term_time_0_30 += move.amount_residual
                            inf['amount']+=move.amount_residual
                        elif deu_time >=31 and deu_time<=60:
                            term_time_31_60 += move.amount_residual
                            inf['amount']+=move.amount_residual
                        elif deu_time >=61 and deu_time<=90:
                            term_time_61_90 += move.amount_residual
                            inf['amount']+=move.amount_residual
                        elif deu_time >90:
                            term_time_90 += move.amount_residual
                            inf['amount']+=move.amount_residual
                        inf['term_time_0_30']+=term_time_0_30
                        inf['term_time_31_60']+=term_time_31_60
                        inf['term_time_61_90']+=term_time_61_90
                        inf['term_time_90']+=term_time_90
                        inf['t_retention_1']+=retention_1
                        inf['t_retention_12_5']+=retention_12_5
            else:
                term_time_0_30=term_time_31_60=term_time_61_90=term_time_90=amount_residual=0
                bank_number='N/A'
                name_partner.append(move.partner_id.name)
                deu_time, term_time = self.calculate_time_date(move.invoice_date,move.invoice_date_due)
                retention_1=retention_12_5=0
                retention_1 = getattr(move, 'ret_amount_1', 0.0)
                retention_12_5 = getattr(move, 'ret_amount_12_5', 0.0)
                name_partner_value.append({
                    'invoice':move.supplier_invoice_number,
                    'invoice_date':self.change_format(move.invoice_date),
                    'invoice_due':self.change_format(move.invoice_date_due),
                    'amount': move.amount_residual,
                    'journal': move.journal_id.name,
                    'deu_time':deu_time, 
                    'term_time':term_time,
                    'debt_days':deu_time-term_time,
                    'retention_1':retention_1,
                    'retention_12_5':retention_12_5,
                    })
                if deu_time >=0 and deu_time<=30:
                    term_time_0_30 += move.amount_residual
                    amount_residual=move.amount_residual
                elif deu_time >=31 and deu_time<=60:
                    term_time_31_60 += move.amount_residual
                    amount_residual=move.amount_residual
                elif deu_time >=61 and deu_time<=90:
                    term_time_61_90 += move.amount_residual
                    amount_residual=move.amount_residual
                elif deu_time >90:
                    term_time_90 += move.amount_residual
                    amount_residual=move.amount_residual
                if move.partner_bank_id:
                    bank_number= move.partner_bank_id.acc_number
                elif len(move.partner_id.bank_ids)>0:
                    bank_number= move.partner_id.bank_ids[0].acc_number
                info.append({
                    'name_supplier': move.partner_id.name,
                    'amount': amount_residual,
                    'value': name_partner_value,
                    'term_time_0_30':term_time_0_30,
                    'term_time_31_60':term_time_31_60,
                    'term_time_61_90':term_time_61_90,
                    'term_time_90':term_time_90,
                    'bank_number': bank_number,
                    't_retention_1':retention_1 or 0,
                    't_retention_12_5':retention_12_5 or 0,
                })
                name_partner_value=[]
        return info

    def change_format(self,date):
        if date:
            date1 = datetime.strptime(str(date), '%Y-%m-%d')
            return date1.strftime('%d/%m/%Y')
        else:
            return date

    def calculate_time_date(self,invoice_date,invoice_due):
        date_date = datetime.strptime(str(invoice_date), DEFAULT_SERVER_DATE_FORMAT)
        due_date = datetime.strptime(str(invoice_due), DEFAULT_SERVER_DATE_FORMAT)
        delta = relativedelta(due_date, date_date)
        times_term = delta.years*365 + delta.months*30 + delta.days
        b_date = datetime.strptime(str(invoice_due), DEFAULT_SERVER_DATE_FORMAT)
        delta = relativedelta(datetime.now(), b_date)
        ####### tiempo 
        times_elapsed = delta.years*365 + delta.months*30 + delta.days
        return times_elapsed,times_term
