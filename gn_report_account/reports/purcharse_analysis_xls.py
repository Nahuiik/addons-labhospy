# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from functools import reduce
# import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
import io
import base64

class PurcharseAnalysisXLSX(models.AbstractModel):
    _name = 'report.gn_report_account.purcharse_xls.xlsx'
    _description = 'Purchase Analysis Report XLS'
    _inherit = 'report.report_xlsx.abstract'
    
    def generate_xlsx_report(self, workbook, data, lines):
        cont = 1
        company_name = self.env.user.company_id.name
        sheet = workbook.add_worksheet(_('Purcharse Analysis'))
        info = self.get_data(data.get('start_date'),data.get('end_date'))
        cont+=1
        
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
        sheet.set_column(7, 7, 9)
        sheet.set_column(8, 8, 9)
        sheet.set_column(9, 9, 12)
        sheet.set_column(10, 10, 9)
        sheet.set_column(11, 11, 12)
        sheet.set_column(12, 12, 15)
        sheet.set_column(13, 13, 20)
        sheet.set_column(14, 14, 17)
        sheet.set_row(7,32)
        buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
        sheet.insert_image('B2', "any_name.png", {'image_data': buf_image, 'x_scale': 0.147, 'y_scale': 0.153,})
        sheet.merge_range('A3:L3', company_name, format11)
        sheet.merge_range('A4:L4', _('REPORT PURCHARSE ANALYSIS'), format11)

        sheet.merge_range('A6:B6', _('Start Date: %s')%(self.change_format(data.get('start_date'))), format24)
        sheet.merge_range('C6:D6', _('End Date: %s')%(self.change_format(data.get('end_date'))), format24)
        sheet.merge_range('E6:F6', _('Print Date: %s')%(datetime.today().strftime('%Y-%m-%d')), format24)

        pos = 7
        num = 1
        total = 0
        sheet.write(7, 0, _('No.'), format21)
        sheet.write(7, 1, _('Date Order'), format21)
        sheet.write(7, 2, _('Name Supplier'), format21)
        sheet.write(7, 3, _('Order Purcharse'), format21)
        sheet.write(7, 4, _('Category'), format21)
        sheet.write(7, 5, _('Type Product Hospitable'), format21)
        sheet.write(7, 6, _('Name Product'), format21)
        sheet.write(7, 7, _('Quantity'), format21)
        sheet.write(7, 8, _('Cost Product Order'), format21)
        sheet.write(7, 9, _('Price Purcharse Average'), format21)
        sheet.write(7, 10, _('Coste Price in product'), format21)
        pos+=1
        for inv in info:
            sheet.write(pos,0, num,format25)
            sheet.write(pos,1, inv.get('date_order'),format22)
            sheet.write(pos,2, inv.get('name_partner'),format22)
            sheet.write(pos,3, inv.get('OrderPurcharse'),format22)
            sheet.write(pos,4, inv.get('Category'),format22)
            sheet.write(pos,5, inv.get('TypeProductHospitable'),format22)
            sheet.write(pos,6, inv.get('Product'),format22)
            sheet.write(pos,7, inv.get('Quantity'),format22)
            sheet.write(pos,8, inv.get('costePrice'),format3)
            sheet.write(pos,9, inv.get('PricePurcharseAverage'),format3)
            sheet.write(pos,10, inv.get('AverageCost'),format3)
            pos+=1
            num+=1

    def get_data(self, start_date, end_date):
        info = []
        domain = [
            ('state', 'in', ['purchase', 'done']),
        ]
        if start_date:
            domain.append(('date_approve', '>=', start_date))
        if end_date:
            domain.append(('date_approve', '<=', end_date))

        orders = self.env['purchase.order'].search(domain)
        for order in orders:
            for line in order.order_line:
                info.append({
                    'date_order': self.change_format_data(order.date_approve or order.date_order),
                    'name_partner': order.partner_id.name or '',
                    'OrderPurcharse': order.name,
                    'Category': line.product_id.categ_id.name or '',
                    'TypeProductHospitable': self.get_type_product(line.product_id.type),
                    'Product': line.product_id.display_name,
                    'Quantity': line.product_qty,
                    'AverageCost': line.product_id.standard_price,
                    'PricePurcharseAverage': self._get_average_purchase_price(line.product_id, start_date, end_date),
                    'costePrice': line.price_unit,
                })
        return info
    def change_format(self, date):
        if not date:
            return ''
        if isinstance(date, datetime):
            return date.strftime('%d/%m/%Y')
        if isinstance(date, str):
            try:
                parsed = datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                return date
            return parsed.strftime('%d/%m/%Y')
        return str(date)

    def change_format_data(self, value):
        if not value:
            return ''
        if isinstance(value, datetime):
            return value.strftime('%d/%m/%Y')
        if isinstance(value, str):
            for fmt in (DEFAULT_SERVER_DATETIME_FORMAT, '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                try:
                    parsed = datetime.strptime(value, fmt)
                    return parsed.strftime('%d/%m/%Y')
                except ValueError:
                    continue
            return value
        return str(value)
    def get_type_product(self,name):
        string_type=""
        if name == 'product':
            string_type='Almacenable'
        elif name == 'service':
            string_type='Servicio'
        elif name=='consu':
            string_type='Consumible'
        if string_type:
            return string_type
        else:
            return name
            

    def _get_average_purchase_price(self, product, start_date, end_date):
        domain = [('state', 'in', ['purchase', 'done']), ('product_id', '=', product.id)]
        if start_date:
            domain.append(('order_id.date_approve', '>=', start_date))
        if end_date:
            domain.append(('order_id.date_approve', '<=', end_date))
        lines = self.env['purchase.order.line'].search(domain)
        amounts = [line.price_unit for line in lines if line.price_unit]
        if not amounts:
            return 0.0
        return sum(amounts) / len(amounts)
