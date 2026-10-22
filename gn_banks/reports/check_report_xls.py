# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
import base64
from datetime import datetime
#import datetime
import xlsxwriter
import io
import xlwt
from odoo.exceptions import UserError


class CheckReportData(models.AbstractModel):
    _name = 'report.gn_banks.check_report.xls'
    _inherit = 'report.report_xlsx.abstract'
    _description = "Banks - Cheque Report"

    
    def generate_xlsx_report(self, workbook, data, lines):
        worksheet = workbook.add_worksheet("Reporte de Cheques")


        row = 9

        # create style for cell
        data_style_yellow = workbook.add_format({
            'font_size': 10,
            'bold': 1,
            'bg_color': '#f7df05'
        })
        data_style_heading = workbook.add_format({
            'font_size': 15,
            'bold': 1,
            'align': 'center',
            'font': 'Times New Roman',
        })

        data_style = workbook.add_format({
            'font_size': 10,
            'bold': 1,
            'border': 1,
            'bg_color':'#088A08',
            'font_color':'#ffffff',
            'align': 'center'
        })

        data_style_align_center = workbook.add_format({
            'font_size': 10,
            'bold': 1,
            'border': 1,
            'align': 'left',
        })

        data_style_normal = workbook.add_format({
            'font_size': 10,
            'bold': 0,
            'align': 'top',
            'border': 0,
            'text_wrap': True
        })

        data_style_number = workbook.add_format({
            'font_size': 10,
            'bold': 0,
            'align': 'top',
            'border': 0,
            'text_wrap': True,
            'num_format': '#,##0.00'
        })

        data_style_pay_to = workbook.add_format({
            'font_size': 10,
            'bold': 0,
            'border': 0,
            'text_wrap': True,
        })

        worksheet.set_column(0, 0, 5)
        worksheet.set_column(1, 1, 12)  # width for number
        worksheet.set_column(2, 2, 12) # width for pay to
        worksheet.set_column(3, 3, 35) # width for jorunal
        worksheet.set_column(4, 4, 35)
        worksheet.set_column(5, 5, 15)
        worksheet.set_column(6, 6, 15) # width for jorunal
        worksheet.set_column(7, 7, 42) # width for jorunal
        worksheet.set_column(8, 8, 42)
        worksheet.set_column(9, 9, 15)
        worksheet.set_column(10, 10, 15)

        if data.get('other'):
            wizard_id = self.env['banks.reports'].browse(int(data.get('wizard_id')))
        else:
            wizard_id = self.env['gn_banks.report.wizard'].browse(int(data.get('wizard_id')))
        worksheet.merge_range('D2:H2', 'Reporte Detallado de Cheques', data_style_heading)
        if wizard_id.start_date and wizard_id.end_date:
            worksheet.merge_range('D4:H4', 'Fecha: %s a %s'%(self.change_format(wizard_id.start_date), self.change_format(wizard_id.end_date)), data_style_align_center)


        #header of file
        worksheet.write('A6:A6', 'N°', data_style)
        worksheet.write('B6:B6', 'Fecha', data_style)
        worksheet.write('C6:C6', 'Chq#', data_style)
        worksheet.write('D6:D6', 'Pagar a', data_style)
        worksheet.write('E6:E6', 'Banco', data_style)
        worksheet.write('F6:F6', 'Monto', data_style)
        worksheet.write('G6:G6', 'Estado', data_style)
        worksheet.write('H6:H6', 'Cuenta', data_style)
        worksheet.write('I6:I6', 'Descripción', data_style)
        worksheet.write('J6:J6', 'Debito', data_style)
        worksheet.write('K6:K6', 'Crédito', data_style)


        domain = [('move_type','=','check')]
        payment_domain = [('state','=','posted'),('partner_type','=','supplier'),('payment_move_type','in',['check','transference'])]
        #print('======0<<<',payment_domain)
        #print('================',wizard_id.start_date,self.change_format(wizard_id.start_date),wizard_id.end_date)
        #print(po)
        if wizard_id.start_date:
            domain.append(('date', '>=', wizard_id.start_date))
            payment_domain.append(('date', '>=', wizard_id.start_date))
        if wizard_id.end_date:
            domain.append(('date', '<=', wizard_id.end_date))
            payment_domain.append(('date', '<=', wizard_id.end_date))

        check_ids = self.env['bank.check'].search(domain)
        payment_ids = self.env['account.payment'].search(payment_domain)

        row = 6
        cols = 0
        num = 1
        for check in check_ids:
            state = ''
            if check.state == 'validated':
                state = 'Validado'

            worksheet.write(row, cols, num, data_style)
            worksheet.write(row, cols + 1, self.change_format(check.date) or '', data_style_normal)
            worksheet.write(row, cols + 2, check.name or '', data_style_normal)
            worksheet.write(row, cols + 3, check.partner_id.name or '', data_style_normal)
            worksheet.write(row, cols + 4, check.journal_id.display_name or '', data_style_normal)
            worksheet.write(row, cols + 5, check.total or 0, data_style_number)
            worksheet.write(row, cols + 6, state or '', data_style_normal)

            if not check.check_lines:
                row += 1
            for line in check.check_lines:
                worksheet.write(row, cols + 7, line.account_id.display_name or '', data_style_normal)
                worksheet.write(row, cols + 8, line.name or '', data_style_normal)
                if line.move_type1 == 'debit':
                    worksheet.write(row, cols + 9, line.amount or 0, data_style_number)
                    worksheet.write(row, cols + 10, 0, data_style_number)
                if line.move_type1 == 'credit':
                    worksheet.write(row, cols + 9, 0, data_style_number)
                    worksheet.write(row, cols + 10, line.amount or 0, data_style_number)

                row += 1
            num += 1

        for payment in payment_ids:
            state = ''
            if payment.state == 'posted':
                state = 'Validado'

            worksheet.write(row, cols, num, data_style)
            worksheet.write(row, cols + 1, self.change_format(str(payment.date)) or '', data_style_normal)
            worksheet.write(row, cols + 2, payment.name or '', data_style_normal)
            worksheet.write(row, cols + 3, payment.partner_id.name or '', data_style_normal)
            worksheet.write(row, cols + 4, payment.journal_id.display_name or '', data_style_normal)
            worksheet.write(row, cols + 5, payment.amount or 0, data_style_number)
            worksheet.write(row, cols + 6, state or '', data_style_normal)
            if not payment.line_ids:
                row += 1
            for line in payment.line_ids:
                worksheet.write(row, cols + 7, line.account_id.display_name or '', data_style_normal)
                worksheet.write(row, cols + 8, line.name or '', data_style_normal)
                if line.debit > 0:
                    worksheet.write(row, cols + 9, line.debit or 0, data_style_number)
                    worksheet.write(row, cols + 10, 0, data_style_number)
                if line.credit > 0:
                    worksheet.write(row, cols + 9, 0, data_style_number)
                    worksheet.write(row, cols + 10, line.credit or 0, data_style_number)

                row += 1
            num += 1
            # worksheet.write(row, cols, check.date, data_style)
            # worksheet.write(row, cols, check.date, data_style)
            # worksheet.write(row, cols, check.date, data_style)
            # worksheet.write(row, cols, check.date, data_style)

    def change_format(self,date):
        if date:
            try:
                date1 = datetime.strptime(str(date), '%Y-%m-%d')
                return date1.strftime('%d/%m/%Y')
            except:
                return ''
        return ''