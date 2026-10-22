# -*- coding: utf-8 -*-
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, api, fields
from datetime import datetime
import io
import base64

class wireTransferReportXlsx(models.AbstractModel):
    _name = 'report.gn_banks.wire_transfer_report_xls.xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'report gn_banks wire_transfer_report_xls xlsx'

    def generate_xlsx_report(self, workbook, data, lines):
        cont = 1
        company_name = self.env.company.name
        sheet = workbook.add_worksheet('Transferencias Bancarias')
        info = self.get_data(data.get('start_date'),data.get('end_date'))
        #buf_image = io.BytesIO(base64.b64decode(self.env.company.logo))
        #sheet.insert_image('A1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.8, 'y_scale': 0.9,})

        cont+=1
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format23 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format24 = workbook.add_format({'font_size': 10, 'align': 'right', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'left', 'left':False,'right':False,'bottom': False, 'top': False, 'bold':False ,'font_size': 10,'num_format': 'L '+'#,##0.00'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 10)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 3, 40)
        sheet.set_column(4, 4, 35)
        sheet.set_column(5, 5, 15)
        sheet.set_column(6, 6, 40)
        sheet.set_column(7, 7, 35)
        sheet.set_column(8, 8, 15)
        sheet.set_column(9, 9, 15)

        sheet.merge_range('B3:J3', company_name, format11)
        sheet.merge_range('B4:J4', 'TRANSFERENCIAS BANCARIAS', format11)

        sheet.merge_range('B6:C6', 'Fecha Inicio: %s'%(data.get('start_date') or ''), format23)
        sheet.merge_range('D6:E6', 'Fecha Fin: %s'%(data.get('end_date') or ''), format23)

        pos = 8
        num = 1
        total_debit = 0
        total_credit = 0
        sheet.write(7, 0, 'N°', format21)
        sheet.write(7, 1, 'Fecha', format21)
        sheet.write(7, 2, 'Número', format21)
        sheet.write(7, 3, 'Pagar a', format21)
        sheet.write(7, 4, 'Banco', format21)
        sheet.write(7, 5, 'Monto', format21)
        sheet.write(7, 6, 'Cuenta', format21)
        sheet.write(7, 7, 'Descripción', format21)
        sheet.write(7, 8, 'Debito', format21)
        sheet.write(7, 9, 'Crédito', format21)
        for dep in info:
            sheet.write(pos, 0, num, format25)
            sheet.write(pos, 1, dep.get('date') or '', format22)
            sheet.write(pos, 2, dep.get('number') or '', format22)
            sheet.write(pos, 3, dep.get('payment_to') or '', format22)
            sheet.write(pos, 4, dep.get('journal') or '', format22)
            sheet.write_number(pos, 5, dep.get('amount') or 0, format3)
            for line in dep.get('lines'):
                sheet.write(pos, 6, line.get('account') or '', format22)
                sheet.write(pos, 7, line.get('description') or '', format22)
                sheet.write_number(pos, 8, line.get('debit') or 0, format3)
                sheet.write_number(pos, 9, line.get('credit') or 0, format3)
                pos+=1
                total_debit += line.get('debit')
                total_credit += line.get('credit')
            num+=1
        sheet.write(pos, 7, "TOTAL:", format24)
        sheet.write_number(pos, 8, total_debit or 0, format4)
        sheet.write_number(pos, 9, total_credit or 0, format4)

    def get_data(self, start_date, end_date):
        transfer_ids = self.env['bank.check'].search([('date','>=',start_date),('date','<=',end_date),('move_type','=','transference'),('state','=','validated')])
        account_payments = self.env['account.payment'].search([('date','>=',start_date),('date','<=',end_date),('payment_move_type','=','transference'),('state','=','posted')])
        info = []
        for transfer in transfer_ids:
            lines = []
            for line in transfer.check_lines:
                credit = 0
                debit = 0
                if line.move_type1 == 'credit':
                    credit = line.amount or 0
                elif line.move_type1 == 'debit':
                    debit = line.amount or 0
                lines.append({
                    'account': line.account_id.display_name or '',
                    'description': line.name or '',
                    'debit': debit,
                    'credit': credit
                })

            info.append({
                'date': self.change_format(transfer.date) or '',
                'number': transfer.name or '',
                'journal': transfer.journal_id.name or '',
                'amount': transfer.total or 0,
                'payment_to': transfer.partner_id.name or '',
                'lines': lines
            })
        for payment in account_payments:
            lines=[]
            for line in payment.line_ids:
                lines.append({
                    'account': line.account_id.display_name or '',
                    'description': line.name or '',
                    'debit': line.debit or 0,
                    'credit': line.credit or 0,
                })
            info.append({
                'date': self.change_format(str(payment.date)) or '',
                'number': payment.name or '',
                'journal': payment.journal_id.name or '',
                'amount': payment.amount or 0,
                'payment_to': payment.partner_id.name or '',
                'lines': lines
            })
        return info

    def change_format(self,date):
        if date:
            try:
                date1 = datetime.strptime(str(date), '%Y-%m-%d')
                return date1.strftime('%d/%m/%Y')
            except:
                return ''
        return ''