# -*- coding: utf-8 -*-
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, api, fields, _
from datetime import datetime
import io
import base64

class transferBanksReportXlsx(models.AbstractModel):
    _name = 'report.gn_banks.transfer_banks_report_xls.xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'report gn_banks transfer_banks_report_xls xlsx'

    def generate_xlsx_report(self, workbook, data, lines):
        cont = 1
        company_name = self.env.company.name
        sheet = workbook.add_worksheet('Transferencia entre Bancos')
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
        sheet.set_column(2, 2, 18)
        sheet.set_column(3, 3, 35)
        sheet.set_column(4, 4, 35)
        sheet.set_column(5, 5, 40)
        sheet.set_column(6, 6, 15)
        sheet.set_column(7, 7, 15)

        sheet.merge_range('B3:H3', company_name, format11)
        sheet.merge_range('B4:H4', 'TRANSFERENCIA ENTRE BANCOS', format11)

        sheet.merge_range('B6:C6', 'Fecha Inicio: %s'%(data.get('start_date') or ''), format23)
        sheet.merge_range('D6:E6', 'Fecha Fin: %s'%(data.get('end_date') or ''), format23)

        pos = 8
        num = 1
        total = 0
        sheet.write(7, 0, 'N°', format21)
        sheet.write(7, 1, 'Fecha', format21)
        sheet.write(7, 2, 'Número', format21)
        sheet.write(7, 3, 'Banco', format21)
        sheet.write(7, 4, 'A Banco', format21)
        sheet.write(7, 5, 'Descripción', format21)
        sheet.write(7, 6, 'Monto', format21)
        for bank in info:
            sheet.write(pos, 0, num, format25)
            sheet.write(pos, 1, bank.get('date') or '', format22)
            sheet.write(pos, 2, bank.get('number') or '', format22)
            sheet.write(pos, 3, bank.get('bank') or '', format22)
            sheet.write(pos, 4, bank.get('to_bank') or '', format22)
            sheet.write(pos, 5, bank.get('description') or '', format22)
            sheet.write_number(pos, 6, bank.get('amount') or 0, format3)
            total += bank.get('amount')
            pos+=1
            num+=1
        sheet.write(pos, 5, "TOTAL:", format24)
        sheet.write_number(pos, 6, total or 0, format4)

    def get_data(self, start_date, end_date):
        transfer_bank_ids = self.env['bank.transfer'].search([('date','>=',start_date),('date','<=',end_date),('state','=','validated')])
        info = []
        for bank in transfer_bank_ids:
            info.append({
                'date': self.change_format(bank.date) or '',
                'number': bank.name or '',
                'description': bank.description or '',
                'bank': bank.journal_id.name or '',
                'to_bank': bank.dest_journal_id.name or '',
                'amount': bank.total or 0,
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