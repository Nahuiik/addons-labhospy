# -*- coding: utf-8 -*-
from odoo import models


class GnStockKardexSummaryXlsx(models.AbstractModel):
    _name = 'report.gn_stock_kardex.stock_kardex_summary_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Kardex Summary XLSX'

    def generate_xlsx_report(self, workbook, data, objs):
        wizard = objs[0]
        report = self.env['report.gn_stock_kardex.report_kardex_template']
        products = wizard._resolve_products()
        branch_id = wizard.branch_id.id if wizard.branch_id else False
        warehouse_id = wizard.warehouse_id.id if wizard.warehouse_id else False
        location_id = wizard.location_id.id if wizard.location_id else False
        vals = report._get_summary_data(
            wizard.company_id, products, wizard.date_from, wizard.date_to,
            branch_id=branch_id, warehouse_id=warehouse_id, location_id=location_id,
        )

        sheet = workbook.add_worksheet('Resumen Kardex')

        # Formats
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center',
            'bg_color': '#5B2C6F', 'font_color': 'white',
        })
        subtitle_fmt = workbook.add_format({'bold': True, 'font_size': 10})
        hdr_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#5B2C6F', 'font_color': 'white',
            'border': 1, 'align': 'center', 'font_size': 9,
        })
        cat_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#f0f0f0',
            'bottom': 2, 'bottom_color': '#5B2C6F',
        })
        cell_fmt = workbook.add_format({'border': 1, 'font_size': 9})
        num_fmt = workbook.add_format({
            'border': 1, 'num_format': '#,##0.00', 'font_size': 9,
        })
        total_label_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'font_size': 9, 'align': 'right',
            'bg_color': '#e8e4ed',
        })
        total_num_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'num_format': '#,##0.00',
            'font_size': 9, 'bg_color': '#e8e4ed',
        })
        total_dash_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'font_size': 9, 'align': 'center',
            'bg_color': '#e8e4ed',
        })

        # Title
        sheet.merge_range(0, 0, 0, 6, 'REPORTE KARDEX — MÉTODO PROMEDIO', title_fmt)
        row = 1
        sheet.write(row, 0, 'NIT:', subtitle_fmt)
        row += 1
        sheet.write(row, 0, 'COMPAÑÍA:', subtitle_fmt)
        sheet.write(row, 1, vals['company'].name)
        row += 1
        sheet.write(row, 0, 'PERIODO:', subtitle_fmt)
        sheet.write(row, 1, f"Desde {vals['date_from']} 00:00:00 hasta {vals['date_to']} 23:59:59")
        row += 2

        # Headers
        headers = ['Producto', 'Saldo Inicial', 'Entradas', 'Salidas',
                    'Saldo Final', 'Costo Unit. Final', 'Total Final']
        for col, h in enumerate(headers):
            sheet.write(row, col, h, hdr_fmt)
        row += 1

        for cat in vals.get('categories', []):
            sheet.merge_range(row, 0, row, 6, f"Categoría: {cat['name']}", cat_fmt)
            row += 1
            for r in cat['rows']:
                sheet.write(row, 0, r['product'].display_name, cell_fmt)
                sheet.write(row, 1, r['opening_qty'], num_fmt)
                sheet.write(row, 2, r['incoming'], num_fmt)
                sheet.write(row, 3, r['outgoing'], num_fmt)
                sheet.write(row, 4, r['closing_qty'], num_fmt)
                sheet.write(row, 5, r['closing_unit_cost'], num_fmt)
                sheet.write(row, 6, r['closing_total'], num_fmt)
                row += 1
            # Category subtotal
            sheet.write(row, 0, 'Total', total_label_fmt)
            sheet.write(row, 1, cat['opening'], total_num_fmt)
            sheet.write(row, 2, cat['incoming'], total_num_fmt)
            sheet.write(row, 3, cat['outgoing'], total_num_fmt)
            sheet.write(row, 4, cat['closing_qty'], total_num_fmt)
            sheet.write(row, 5, '-', total_dash_fmt)
            sheet.write(row, 6, cat['closing_total'], total_num_fmt)
            row += 1
            row += 1  # blank row between categories

        # Column widths
        sheet.set_column(0, 0, 38)
        sheet.set_column(1, 6, 16)
