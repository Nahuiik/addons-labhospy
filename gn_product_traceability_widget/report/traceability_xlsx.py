# -*- coding: utf-8 -*-

from odoo import _, models


class ReportTraceabilityXlsx(models.AbstractModel):
    _name = 'report.gn_traceability.traceability_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Product Traceability XLSX Report'

    def generate_xlsx_report(self, workbook, data, objects):
        filters = (data or {}).get('filters') or {}
        payload = self.env['product.traceability.service'].get_export_data(filters)
        product = payload['product']
        summary = payload['summary']
        show_costs = (payload.get('meta') or {}).get('can_show_costs')

        bold = workbook.add_format({'bold': True})
        header = workbook.add_format({'bold': True, 'bg_color': '#2563eb', 'font_color': '#ffffff'})
        num = workbook.add_format({'num_format': '#,##0.00'})

        # Sheet 1: Summary
        sheet_sum = workbook.add_worksheet(_('Resumen'))
        sheet_sum.write(0, 0, _('Trazabilidad de producto'), bold)
        rows = [
            (_('Producto'), product.get('name')),
            (_('Referencia'), product.get('default_code')),
            (_('Compañía'), payload.get('company', {}).get('name')),
            (_('Lote/Serie'), (product.get('lot') or {}).get('name', '')),
            (_('Saldo inicial'), summary.get('opening_qty')),
            (_('Entradas'), summary.get('incoming_qty')),
            (_('Salidas'), summary.get('outgoing_qty')),
            (_('Saldo final'), summary.get('closing_qty')),
        ]
        if show_costs:
            rows.extend([
                (_('Valor inicial'), summary.get('opening_value_fmt') or summary.get('opening_value')),
                (_('Valor entradas'), summary.get('incoming_value_fmt') or summary.get('incoming_value')),
                (_('Valor salidas'), summary.get('outgoing_value_fmt') or summary.get('outgoing_value')),
                (_('Valor final'), summary.get('closing_value_fmt') or summary.get('closing_value')),
                (_('Costo promedio'), product.get('avg_cost_fmt') or product.get('avg_cost')),
                (_('Valor en existencia'), product.get('total_value_fmt') or product.get('total_value')),
            ])
        rows.extend([
            (_('Generado por'), payload.get('generated_by')),
            (_('Fecha'), payload.get('generated_at')),
        ])
        row_idx = 2
        for label, value in rows:
            sheet_sum.write(row_idx, 0, label, bold)
            if isinstance(value, (int, float)):
                sheet_sum.write(row_idx, 1, value, num)
            else:
                sheet_sum.write(row_idx, 1, value or '')
            row_idx += 1

        # Totals by movement type on summary sheet
        row_idx += 1
        sheet_sum.write(row_idx, 0, _('Totales por tipo de movimiento'), bold)
        row_idx += 1
        type_headers = [_('Tipo'), _('Cantidad'), _('Entrada'), _('Salida')]
        if show_costs:
            type_headers.extend([_('Valor entrada'), _('Valor salida')])
        sheet_sum.write_row(row_idx, 0, type_headers, header)
        row_idx += 1
        for item in payload.get('movement_summary', []):
            sheet_sum.write(row_idx, 0, item.get('label'))
            sheet_sum.write(row_idx, 1, item.get('count') or 0)
            sheet_sum.write(row_idx, 2, item.get('qty_in') or 0, num)
            sheet_sum.write(row_idx, 3, item.get('qty_out') or 0, num)
            if show_costs:
                sheet_sum.write(row_idx, 4, item.get('value_in') or 0, num)
                sheet_sum.write(row_idx, 5, item.get('value_out') or 0, num)
            row_idx += 1

        # Current locations on summary
        if payload.get('current_locations'):
            row_idx += 1
            sheet_sum.write(row_idx, 0, _('Ubicación actual'), bold)
            row_idx += 1
            sheet_sum.write_row(row_idx, 0, [_('Ubicación'), _('Disponible'), _('Reservado')] + ([_('Valor')] if show_costs else []), header)
            row_idx += 1
            for loc in payload['current_locations']:
                sheet_sum.write(row_idx, 0, loc.get('location'))
                sheet_sum.write(row_idx, 1, loc.get('qty') or 0, num)
                sheet_sum.write(row_idx, 2, loc.get('reserved') or 0, num)
                if show_costs:
                    sheet_sum.write(row_idx, 3, loc.get('value') or 0, num)
                row_idx += 1

        sheet_sum.set_column(0, 0, 28)
        sheet_sum.set_column(1, 3, 16)

        # Sheet 2: Movements
        sheet_mov = workbook.add_worksheet(_('Movimientos'))
        columns = [
            _('Fecha'), _('Tipo'), _('Documento'), _('Origen'), _('Destino'),
            _('Entrada'), _('Salida'), _('Saldo'), _('UoM'), _('Lote/Serie'),
            _('Proveedor'), _('Cliente'), _('Responsable'), _('Estado'),
        ]
        if show_costs:
            columns[8:8] = [
                _('Costo unit.'), _('Valor entrada'), _('Valor salida'), _('Saldo valor'),
            ]
        for col, title in enumerate(columns):
            sheet_mov.write(0, col, title, header)
        sheet_mov.freeze_panes(1, 0)
        events = payload.get('events', [])
        sheet_mov.autofilter(0, 0, max(len(events), 1), len(columns) - 1)

        for mov_row, event in enumerate(events, start=1):
            sheet_mov.write(mov_row, 0, event.get('date_fmt') or event.get('date'))
            sheet_mov.write(mov_row, 1, event.get('type_label'))
            sheet_mov.write(mov_row, 2, event.get('document'))
            sheet_mov.write(mov_row, 3, event.get('source'))
            sheet_mov.write(mov_row, 4, event.get('destination'))
            sheet_mov.write(mov_row, 5, event.get('in_qty') or 0, num)
            sheet_mov.write(mov_row, 6, event.get('out_qty') or 0, num)
            sheet_mov.write(mov_row, 7, event.get('balance') or 0, num)
            col = 8
            if show_costs:
                sheet_mov.write(mov_row, col, event.get('unit_cost') or 0, num)
                sheet_mov.write(mov_row, col + 1, event.get('value_in') or 0, num)
                sheet_mov.write(mov_row, col + 2, event.get('value_out') or 0, num)
                sheet_mov.write(mov_row, col + 3, event.get('value_balance') or 0, num)
                col += 4
            sheet_mov.write(mov_row, col, event.get('uom'))
            sheet_mov.write(mov_row, col + 1, event.get('lot'))
            sheet_mov.write(mov_row, col + 2, event.get('supplier'))
            sheet_mov.write(mov_row, col + 3, event.get('customer'))
            sheet_mov.write(mov_row, col + 4, event.get('user'))
            sheet_mov.write(mov_row, col + 5, event.get('state_label'))

        for col in range(len(columns)):
            sheet_mov.set_column(col, col, 16)

        code = product.get('default_code') or 'product'
        date_from = (payload.get('filters') or {}).get('date_from') or ''
        date_to = (payload.get('filters') or {}).get('date_to') or ''
        workbook.set_properties({
            'title': f'Trazabilidad_{code}_{date_from}_{date_to}',
        })
