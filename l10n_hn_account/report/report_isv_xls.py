# -*- coding: utf-8 -*-
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, api, fields, _
from datetime import datetime
import io
import base64

class isvReportXlsx(models.AbstractModel):
    _name = 'report.l10n_hn_account.isv_report_xls.xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Description'

    def generate_xlsx_report(self, workbook, data, lines):
        month = self.get_month(data.get('month'))
        credit = data.get('fiscal_credit')
        pos = data.get('pos')
        isv_report = self.env['report.l10n_hn_account.isv_report_view'].get_data(month,credit,pos)
        cont = 1
        company_name = self.env.user.company_id.name
        sheet = workbook.add_worksheet(_('ISV'))

        #buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
        #sheet.insert_image('D1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.8, 'y_scale': 0.9,})

        cont+=1
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': True,'bottom': False, 'top': False, 'bold': False})
        format22 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True,'bottom': False, 'top': True, 'bold': True})
        format23 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': False, 'top': False, 'bold': False})
        format24 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': True,'bottom': True, 'top': False, 'bold': False})
        
        format25 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format26 = workbook.add_format({'font_size': 11, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right','left':False,'right':True,'bottom': True, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right','left':False,'right':True,'bottom': False, 'top': False, 'bold':False ,'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'bold':False ,'font_size': 10,'num_format': '#,##0.00'})
        format6 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'bold':True ,'font_size': 11,'num_format': '#,##0.00'})
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
        sheet.set_column(3, 3, 15)
        sheet.set_column(4, 4, 8)
        sheet.set_column(5, 5, 20)
        sheet.set_column(6, 6, 8)
        sheet.set_column(7, 7, 40)
        sheet.set_column(8, 8, 40)


        pos = 9
        for o in isv_report:
            sheet.merge_range('B4:C4', company_name, format11)
            sheet.merge_range('B5:C5', _('Sales Tax Report'), format11)
            sheet.merge_range('B6:C6', _('Month: %s %s')%(month,o.get('year')), format11)
            sheet.merge_range('B8:C8', _('Sales Summary'), format22)
            sheet.merge_range('B9:C9', '', format23)
            sheet.write(pos, 1, _('Net Sale %s')%(company_name), format21)
            sheet.write_number(pos, 2, o.get('net_sale'), format4)
            pos+=1
            sheet.write(pos, 1, _('Taxed Sale 15%'), format21)
            sheet.write_number(pos, 2, o.get('taxed_sale'), format4)
            pos+=1
            sheet.write(pos, 1, _('Exonerated Sale'), format21)
            sheet.write_number(pos, 2, o.get('exonerated_sale'), format4)
            pos+=1
            sheet.write(pos, 1, _('Total Sale'), format24)
            sheet.write_number(pos, 2, o.get('total_sale'), format3)
            pos+=4

            sheet.merge_range('B15:C15', _('Importation Summary'), format22)
            sheet.merge_range('B16:C16', '', format23)
            sheet.write(pos, 1, _('Importation'), format21)
            sheet.write_number(pos, 2, 0, format4)
            pos+=1
            sheet.write(pos, 1, _('Taxed Purchase 15%'), format21)
            sheet.write_number(pos, 2, 0, format4)
            sheet.merge_range('B19:C19', '', format23)
            pos+=2
            sheet.write(pos, 1, _('Total Purchase'), format24)
            sheet.write_number(pos, 2, 0, format3)
            pos+=4

            sheet.merge_range('B22:C22', _('Purchase Summary'), format22)
            sheet.merge_range('B23:C23', '', format23)
            sheet.write(pos, 1, _('Net Purchase %s')%(company_name), format21)
            sheet.write_number(pos, 2, o.get('net_purchase'), format4)
            pos+=1
            sheet.write(pos, 1, _('Taxed Purchase 15%'), format21)
            sheet.write_number(pos, 2, o.get('taxed_purchase'), format4)
            sheet.merge_range('B26:C26', '', format23)
            pos+=2
            sheet.write(pos, 1, _('Total Purchase'), format24)
            sheet.write_number(pos, 2, o.get('total_purchase'), format3)
            pos+=2

            sheet.write(pos, 1, _('Total to Pay'), format25)
            sheet.write_number(pos, 2, o.get('to_pay'), format5)
            pos+=1
            sheet.write(pos, 1, _('(-) Previous Period Tax Credit'), format25)
            sheet.write_number(pos, 2, o.get('credit_fiscal'), format5)
            pos+=1
            sheet.write(pos, 1, _('(-) Tax Withheld POS'), format25)
            sheet.write_number(pos, 2, o.get('pos'), format5)
            pos+=1
            sheet.write(pos, 1, _('Total Tax to be Paid'), format26)
            sheet.write_number(pos, 2, o.get('total'), format6)

    def get_month(self,month):
        if month == 'january':
            return 'Enero'
        elif month == 'february':
            return 'Febrero'
        elif month == 'march':
            return 'Marzo'
        elif month == 'april':
            return 'Abril'
        elif month == 'may':
            return 'Mayo'
        elif month == 'june':
            return 'Junio'
        elif month == 'july':
            return 'Julio'
        elif month == 'august':
            return 'Agosto'
        elif month == 'september':
            return 'Septiembre'
        elif month == 'october':
            return 'Octubre'
        elif month == 'november':
            return 'Noviembre'
        elif month == 'december':
            return 'Diciembre'

    #def change_format(self,date):
    #    return datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')