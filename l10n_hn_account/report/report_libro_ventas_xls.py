# -*- coding: utf-8 -*-
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, api, fields, _
from datetime import datetime

class SalesXlsx(models.AbstractModel):
    _name = 'report.l10n_hn_account.report_libro_ventas_invoice_xls'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Description'

    def generate_xlsx_report(self, workbook, data, lines):
        cont = 1
        company_name = self.env.user.company_id.name
        for sale in lines:
            sheet = workbook.add_worksheet(_('Libro ventas ' + str(cont)))
            cont+=1
            format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
            format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
            format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
            format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#F3F781'})
            format23 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
            format24 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
            ########### NUMBER FORMAT #######################################
            format3 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
            format4 = workbook.add_format({'align':'left','left':False,'right':False,'bottom': False, 'top': False, 'bold':False ,'font_size': 10,'num_format': '#,##0.00'})
            format5 = workbook.add_format({'align':'left','left':False,'right':False,'bottom': False, 'top': False, 'bold':False ,'font_size': 10,'num_format': 'L '+'#,##0.00'})
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
            sheet.set_column(2, 2, 35)
            sheet.set_column(3, 3, 20)
            sheet.set_column(4, 4, 35)
            sheet.set_column(5, 5, 25)
            sheet.set_column(6, 6, 15)
            sheet.set_column(7, 7, 15)
            sheet.set_column(8, 8, 15)
            sheet.set_column(9, 9, 15)
            sheet.set_column(10, 10, 15)
            sheet.set_column(11, 11, 15)
            sheet.set_column(12, 12, 15)
            sheet.set_column(13, 13, 15)

            #sheet.merge_range('A1:I1', company_name, format1)
            sheet.merge_range('B2:N2', company_name, format11)
            
            sheet.write(3, 1, _('Sales book'), format23)
            sheet.merge_range('B5:C5', _('Expressed in Lempiras of Honduras').upper(), format23)
            #sheet.write(4, 1, _('Expressed in Lempiras of Honduras'), format23)

            sheet.write(6, 1, _('Start Date'), format23)
            sheet.write(6, 2, self.change_format(sale.start_date), format24)
            sheet.write(6, 3, _('End Date'), format23)
            sheet.write(6, 4, self.change_format(sale.end_date), format24)

            sheet.write(7, 1, _('Total sales'), format23)
            sheet.write_number(7, 2, sale.total_incoming, format5)
            sheet.write(7, 3, _('Taxable sales'), format23)
            sheet.write_number(7, 4, sale.total_gravado, format5)

            sheet.write(8, 3, _('Ventas Exentas'), format23)
            sheet.write_number(8, 4, sale.total_exento, format5)
            
            sheet.write(9, 3, _('Ventas Exoneradas'), format23)
            sheet.write_number(9, 4, sale.total_exonerate, format5)
            
            sheet.write(10, 3, _('Total taxes'), format23)
            sheet.write_number(10, 4, sale.total_impuesto, format5)
            
            pos = 13
            sheet.write(12, 1, _('Date'), format21)
            sheet.write(12, 2, _('Client'), format21)
            sheet.write(12, 3, _('RTN'), format21)
            sheet.write(12, 4, _('CAI'), format21)
            sheet.write(12, 5, _('Invoice Number'), format21)
            sheet.write(12, 6, _('Subt Total'), format21)
            sheet.write(12, 7, _('Taxed'), format21)
            sheet.write(12, 8, _('Exempt'), format21)
            sheet.write(12, 9, _('Exonerado'), format21)
            sheet.write(12, 10, _('Descuento'), format21)
            sheet.write(12, 11, _('Taxes'), format21)
            sheet.write(12, 12, _('Total'), format21)
            sheet.write(12, 13, _('Type'), format21)
            for invoice in sale.out_invoice_ids:
                discount_amount = sum(invoice.invoice_id.invoice_line_ids.mapped(lambda l: l.price_unit * (l.discount or 0.0) / 100.0 * l.quantity))
                sheet.write(pos, 1, self.change_format(invoice.invoice_date), format22)
                sheet.write(pos, 2, invoice.partner_id.name, format22)
                sheet.write(pos, 3, invoice.partner_id.rtn or '', format22)
                sheet.write(pos, 4, invoice.invoice_id.cai_invoice or '', format22)
                sheet.write(pos, 5, invoice.numero_factura, format22)
                sheet.write_number(pos, 6, invoice.subtotal, format3)
                sheet.write_number(pos, 7, invoice.amount_tax_15_per, format3)
                sheet.write_number(pos, 8, invoice.exempt_sale_amount, format3)
                sheet.write_number(pos, 9, invoice.exonerate_amount, format3)
                sheet.write_number(pos, 10, discount_amount, format3)
                sheet.write_number(pos, 11, invoice.isv, format3)
                sheet.write_number(pos, 12, invoice.total_amount, format3)
                sheet.write(pos, 13, invoice.tipo_factura, format22)
                pos+=1

    def change_format(self,date):
        return datetime.strftime(date,'%d/%m/%Y')
