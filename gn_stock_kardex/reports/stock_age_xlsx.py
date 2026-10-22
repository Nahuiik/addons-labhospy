# -*- coding: utf-8 -*-
from odoo import models


class GnStockAgeXlsx(models.AbstractModel):
    _name = 'report.gn_stock_kardex.stock_age_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Antigüedad de Stock XLSX'

    def generate_xlsx_report(self, workbook, data, objs):
        wizard = objs[0]
        rows, brackets = wizard._compute_age_data()
        bracket_labels = [b[0] for b in brackets]

        sheet = workbook.add_worksheet('Antigüedad de Stock')

        # Formats
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center',
            'bg_color': '#1a1a2e', 'font_color': 'white',
        })
        subtitle_fmt = workbook.add_format({'bold': True, 'font_size': 10})
        hdr_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1a1a2e', 'font_color': 'white',
            'border': 1, 'align': 'center', 'font_size': 9, 'text_wrap': True,
        })
        hdr2_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#2d2d44', 'font_color': '#ddd',
            'border': 1, 'align': 'center', 'font_size': 8,
        })
        cell_fmt = workbook.add_format({'border': 1, 'font_size': 9})
        num_fmt = workbook.add_format({
            'border': 1, 'num_format': '#,##0.00', 'font_size': 9,
        })
        num_bold = workbook.add_format({
            'border': 1, 'num_format': '#,##0.00', 'font_size': 9, 'bold': True,
        })

        num_cols = 4 + len(bracket_labels) * 2
        sheet.merge_range(0, 0, 0, num_cols - 1, 'Reporte de Antigüedad de Stock', title_fmt)

        row = 1
        sheet.write(row, 0, 'Compañía:', subtitle_fmt)
        sheet.write(row, 1, wizard.company_id.name)
        row += 1
        if wizard.warehouse_id:
            sheet.write(row, 0, 'Almacén:', subtitle_fmt)
            sheet.write(row, 1, wizard.warehouse_id.name)
            row += 1
        sheet.write(row, 0, f'Desglose: {wizard.breakdown_days} días', subtitle_fmt)
        row += 2

        # Header row 1
        sheet.merge_range(row, 0, row + 1, 0, 'Producto', hdr_fmt)
        sheet.merge_range(row, 1, row + 1, 1, 'Categoría', hdr_fmt)
        sheet.merge_range(row, 2, row + 1, 2, 'Stock Total', hdr_fmt)
        sheet.merge_range(row, 3, row + 1, 3, 'Valor Stock', hdr_fmt)

        col = 4
        for bl in bracket_labels:
            sheet.merge_range(row, col, row, col + 1, bl, hdr_fmt)
            sheet.write(row + 1, col, 'Stock', hdr2_fmt)
            sheet.write(row + 1, col + 1, 'Valor', hdr2_fmt)
            col += 2
        row += 2

        for r in rows:
            sheet.write(row, 0, r['product_name'], cell_fmt)
            sheet.write(row, 1, r['categ_name'], cell_fmt)
            sheet.write(row, 2, r['total_stock'], num_bold)
            sheet.write(row, 3, r['stock_value'], num_bold)
            col = 4
            for bk in r['buckets']:
                sheet.write(row, col, bk['stock'], num_fmt)
                sheet.write(row, col + 1, bk['value'], num_fmt)
                col += 2
            row += 1

        sheet.set_column(0, 0, 35)
        sheet.set_column(1, 1, 25)
        sheet.set_column(2, num_cols - 1, 14)
