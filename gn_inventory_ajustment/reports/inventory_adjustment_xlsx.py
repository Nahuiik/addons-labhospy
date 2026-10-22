# -*- coding: utf-8 -*-
from odoo import _, fields, models


class GnInventoryAdjustmentXlsx(models.AbstractModel):
    _name = 'report.gn_inventory_ajustment.inventory_adjustment_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Wizard Inventario LabHosPy XLSX'

    def generate_xlsx_report(self, workbook, data, wizards):
        for wizard in wizards:
            self._generate_sheet(workbook, wizard)

    def _generate_sheet(self, workbook, wizard):
        sheet = workbook.add_worksheet(_('Inventario físico'))

        fmt_title = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter',
        })
        fmt_sub = workbook.add_format({'italic': True, 'font_size': 9})
        fmt_head = workbook.add_format({
            'bold': True, 'bg_color': '#D9D9D9', 'border': 1,
            'align': 'center', 'text_wrap': True,
        })
        fmt_cell = workbook.add_format({'border': 1, 'align': 'left'})
        fmt_num = workbook.add_format({
            'border': 1, 'align': 'right', 'num_format': '#,##0.00',
        })
        fmt_blank = workbook.add_format({'border': 1})

        show_qty = wizard.show_qty
        headers = [
            _('Ubicación'),
            _('Código'),
            _('Producto'),
            _('Proveedor'),
            _('Código de Catálogo'),
            _('Modelo'),
            _('Lote/Serie'),
            _('UdM'),
        ]
        if show_qty:
            headers.append(_('A la mano'))
        headers.append(_('Contado'))
        if show_qty:
            headers.append(_('Diferencia'))

        n_cols = len(headers)
        sheet.merge_range(0, 0, 0, n_cols - 1, _('Inventario físico - Hoja de conteo'), fmt_title)
        sheet.write(1, 0, wizard.get_report_filters_label(), fmt_sub)
        sheet.write(2, 0, _('Fecha: %s') % fields.Date.context_today(wizard).strftime('%d/%m/%Y'), fmt_sub)

        header_row = 4
        for col, header in enumerate(headers):
            sheet.write(header_row, col, header, fmt_head)

        row = header_row + 1
        for line in wizard.get_report_lines():
            col = 0
            sheet.write(row, col, line['location'], fmt_cell); col += 1
            sheet.write(row, col, line['default_code'], fmt_cell); col += 1
            sheet.write(row, col, line['product'], fmt_cell); col += 1
            sheet.write(row, col, line['supplier'], fmt_cell); col += 1
            sheet.write(row, col, line['catalog_code'], fmt_cell); col += 1
            sheet.write(row, col, line['model'], fmt_cell); col += 1
            sheet.write(row, col, line['lot'], fmt_cell); col += 1
            sheet.write(row, col, line['uom'], fmt_cell); col += 1
            if show_qty:
                sheet.write(row, col, line['qty_on_hand'], fmt_num); col += 1
            sheet.write(row, col, '', fmt_blank); col += 1  # Contado (en blanco)
            if show_qty:
                sheet.write(row, col, '', fmt_blank)
            row += 1

        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 2, 45)
        sheet.set_column(3, 3, 18)
        sheet.set_column(4, 5, 16)
        sheet.set_column(6, 6, 16)
        sheet.set_column(7, 7, 10)
        sheet.set_column(8, n_cols - 1, 12)
