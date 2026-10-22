# -*- coding: utf-8 -*-
from odoo import models


class GnStockKardexXlsx(models.AbstractModel):
    _name = 'report.gn_stock_kardex.stock_kardex_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Kardex AVCO XLSX'

    def generate_xlsx_report(self, workbook, data, objs):
        wizard = objs[0]
        report = self.env['report.gn_stock_kardex.report_kardex_template']
        vals = report._get_kardex_data(wizard.company_id, wizard.product_ids, wizard.date_from, wizard.date_to)

        sheet = workbook.add_worksheet('Kardex')
        title = workbook.add_format({'bold': True, 'font_size': 12})
        hdr = workbook.add_format({'bold': True, 'bg_color': '#5B2C6F', 'font_color': 'white', 'border': 1})
        cell = workbook.add_format({'border': 1, 'font_size': 9})
        num = workbook.add_format({'border': 1, 'num_format': '#,##0.0000', 'font_size': 9})
        money = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'font_size': 9})
        cmup = workbook.add_format({'border': 1, 'num_format': '#,##0.000000', 'font_size': 9})
        ini_row = workbook.add_format({'border': 1, 'bold': True, 'bg_color': '#f0e6f3', 'font_size': 9})

        row = 0
        sheet.write(row, 0, 'Kardex AVCO', title)
        row += 1
        sheet.write(row, 0, vals['company'].name, cell)
        row += 1
        sheet.write(row, 0, f"Periodo: {vals['date_from']} — {vals['date_to']}", cell)
        row += 2

        for sec in vals['sections']:
            sheet.write(row, 0, sec['product'].display_name, title)
            row += 1
            sheet.write(row, 0, f"Ud. {sec['uom']}", cell)
            row += 1
            headers = ['Fecha', 'Referencia', 'Detalle', 'Entrada', 'Salida', 'Valor mov.', 'Saldo cant.', 'Saldo valor', 'CMUP']
            for col, h in enumerate(headers):
                sheet.write(row, col, h, hdr)
            row += 1
            for line in sec['lines']:
                fmt = ini_row if line.get('es_inicio') else cell
                num_fmt = ini_row if line.get('es_inicio') else num
                money_fmt = ini_row if line.get('es_inicio') else money
                cmup_fmt = ini_row if line.get('es_inicio') else cmup
                sheet.write(row, 0, str(line['date']), fmt)
                sheet.write(row, 1, line['reference'] or '', fmt)
                sheet.write(row, 2, line['description'] or '', fmt)
                sheet.write(row, 3, line['qty_in'], num_fmt)
                sheet.write(row, 4, line['qty_out'], num_fmt)
                sheet.write(row, 5, line['value_move'], money_fmt)
                sheet.write(row, 6, line['balance_qty'], num_fmt)
                sheet.write(row, 7, line['balance_value'], money_fmt)
                sheet.write(row, 8, line['unit_cost'], cmup_fmt)
                row += 1
            row += 1

        sheet.set_column(0, 0, 12)
        sheet.set_column(1, 2, 28)
        sheet.set_column(3, 8, 14)
