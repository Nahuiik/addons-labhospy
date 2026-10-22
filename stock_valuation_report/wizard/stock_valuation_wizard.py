# -*- coding: utf-8 -*-
"""
Wizard optimizado para el reporte de valoración de inventario.
Implementa mejoras de rendimiento:
- Consulta SQL optimizada con CTE
- Pre-carga de datos en batch
- Eliminación de código duplicado
"""

import io
import base64

from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from ..models.stock_valuation_helper import StockValuationHelper

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class StockValuationWizard(models.TransientModel):
    _name = 'stock.valuation.wizard'
    _description = 'Asistente de Reporte de Valoración de Inventario'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    warehouse_ids = fields.Many2many(
        'stock.warehouse',
        string='Almacenes',
        help='Dejar vacío para todos los almacenes'
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        domain="[('usage', '=', 'internal')]",
        help='Dejar vacío para todas las ubicaciones de los almacenes seleccionados'
    )
    start_date = fields.Date(
        string='Fecha Desde',
        required=True,
        default=fields.Date.context_today
    )
    end_date = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.context_today
    )
    filter_product_categ_ids = fields.Many2many(
        'product.category',
        string='Categorías',
        help='Dejar vacío para todas las categorías'
    )
    filter_gn_labhospy_supplier_ids = fields.Many2many(
        'gn.labhospy.supplier',
        'stock_valuation_wiz_labhospy_supplier_rel',
        'wizard_id',
        'supplier_id',
        string='Proveedor (LabHosPy)',
        help='Dejar vacío para todos los proveedores de catálogo'
    )
    only_summary = fields.Boolean(
        string='Solo Resumen',
        help='Si está marcado, solo muestra el resumen por categoría'
    )
    only_with_movement = fields.Boolean(
        string='Solo productos con movimiento',
        default=True,
        help='Si está marcado, solo muestra productos que tienen inventario inicial o movimiento en el período'
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Filtrar almacenes por compañía."""
        self.warehouse_ids = False
        if self.company_id:
            return {
                'domain': {
                    'warehouse_ids': [('company_id', '=', self.company_id.id)]
                }
            }
        return {'domain': {'warehouse_ids': []}}

    @api.onchange('warehouse_ids')
    def _onchange_warehouse_ids(self):
        """Filtrar ubicaciones por almacenes."""
        self.location_id = False
        if self.warehouse_ids:
            view_location_ids = self.warehouse_ids.mapped('view_location_id').ids
            return {
                'domain': {
                    'location_id': [
                        ('location_id', 'child_of', view_location_ids),
                        ('usage', '=', 'internal')
                    ]
                }
            }
        elif self.company_id:
            warehouses = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)])
            view_location_ids = warehouses.mapped('view_location_id').ids
            return {
                'domain': {
                    'location_id': [
                        ('location_id', 'child_of', view_location_ids),
                        ('usage', '=', 'internal')
                    ]
                }
            }
        return {'domain': {'location_id': [('usage', '=', 'internal')]}}

    def _prepare_report_data(self):
        """Preparar datos para el reporte."""
        self.ensure_one()
        
        if self.start_date > self.end_date:
            raise UserError(_('La fecha desde no puede ser mayor que la fecha hasta.'))
        
        return {
            'form': {
                'company_id': [self.company_id.id] if self.company_id else [],
                'warehouse_ids': self.warehouse_ids.ids,
                'location_id': self.location_id.id if self.location_id else False,
                'start_date': self.start_date.strftime(DEFAULT_SERVER_DATE_FORMAT),
                'end_date': self.end_date.strftime(DEFAULT_SERVER_DATE_FORMAT),
                'only_summary': self.only_summary,
                'only_with_movement': self.only_with_movement,
                'filter_product_categ_ids': self.filter_product_categ_ids.ids,
                'filter_gn_labhospy_supplier_ids': self.filter_gn_labhospy_supplier_ids.ids,
            }
        }

    def action_print_pdf(self):
        """Imprimir reporte en PDF."""
        self.ensure_one()
        data = self._prepare_report_data()
        return self.env.ref('stock_valuation_report.action_stock_valuation_report').report_action(self, data=data)

    def _get_locations(self, company_id):
        """Obtener ubicaciones para el reporte."""
        warehouse_ids = self.warehouse_ids.ids if self.warehouse_ids else \
                       StockValuationHelper.find_warehouses(self.env, company_id)
        
        if self.location_id:
            return [self.location_id.id]
        else:
            return StockValuationHelper.find_locations(self.env, warehouse_ids)

    def _get_lines_optimized(self, company_id):
        """
        Obtener líneas del reporte usando consulta optimizada.
        Retorna datos agrupados por categoría con toda la información necesaria.
        """
        locations = self._get_locations(company_id)
        if not locations:
            return {}
        
        start_date = StockValuationHelper.convert_to_utc(self.env, self.start_date, False)
        end_date = StockValuationHelper.convert_to_utc(self.env, self.end_date, True)
        
        return StockValuationHelper.get_movement_data_optimized(
            self._cr,
            start_date,
            end_date,
            locations,
            self.filter_product_categ_ids.ids if self.filter_product_categ_ids else None,
            self.only_with_movement,
            self.filter_gn_labhospy_supplier_ids.ids if self.filter_gn_labhospy_supplier_ids else None,
        )

    def action_print_xlsx(self):
        """Exportar reporte a Excel - Versión optimizada."""
        self.ensure_one()
        
        if self.start_date > self.end_date:
            raise UserError(_('La fecha desde no puede ser mayor que la fecha hasta.'))
        
        company_ids = StockValuationHelper.get_valid_companies(
            self.env, 
            [self.company_id.id] if self.company_id else []
        )
        
        if not company_ids:
            raise UserError(_('No hay almacenes configurados para las compañías seleccionadas.'))
        
        Company = self.env['res.company']
        summary = 'Reporte Resumen' if self.only_summary else 'Reporte Detallado'
        
        # Crear archivo Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Formatos
        main_header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 20, 'bg_color': '#C0C0C0', 'border': 1
        })
        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 9, 'bg_color': '#C0C0C0', 'border': 1
        })
        value_center_format = workbook.add_format({
            'align': 'center', 'valign': 'vcenter',
            'font_size': 9, 'bg_color': '#C0C0C0'
        })
        value_center_purple = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 9, 'font_color': '#800080', 'bg_color': '#C0C0C0'
        })
        data_center = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'font_size': 9, 'bg_color': '#C0C0C0'
        })
        data_right_purple = workbook.add_format({
            'bold': True, 'align': 'right', 'valign': 'vcenter',
            'font_size': 9, 'font_color': '#800080', 'bg_color': '#C0C0C0',
            'num_format': '#,##0.00'
        })
        grand_total_center = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 9, 'font_color': '#800080', 'bg_color': '#C0C0C0', 'border': 1
        })
        grand_total_right = workbook.add_format({
            'bold': True, 'align': 'right', 'valign': 'vcenter',
            'font_size': 9, 'font_color': '#800080', 'bg_color': '#C0C0C0', 'border': 1,
            'num_format': '#,##0.00'
        })
        
        for company_id in company_ids:
            company = Company.browse(company_id)
            sheet = workbook.add_worksheet(company.name[:31])
            
            # Congelar paneles
            sheet.freeze_panes(9, 0)
            
            # Título principal
            sheet.set_row(0, 40)
            sheet.merge_range('A1:M1', company.name, main_header_format)
            
            # Encabezados de información
            sheet.merge_range('A4:B4', 'Fecha', header_format)
            sheet.merge_range('A5:B5', f"{self.start_date} a {self.end_date}", value_center_purple)
            
            sheet.merge_range('C4:D4', 'Compañía', header_format)
            sheet.merge_range('C5:D5', company.name, value_center_format)
            
            sheet.merge_range('E4:F4', 'Almacén(es)', header_format)
            warehouses_name = StockValuationHelper.get_warehouses_name(
                self.env, self.warehouse_ids.ids, company_id
            )
            sheet.merge_range('E5:F5', warehouses_name, value_center_format)
            
            sheet.merge_range('G4:H4', 'Moneda', header_format)
            sheet.merge_range('G5:H5', company.currency_id.name, value_center_format)
            
            sheet.merge_range('I4:J4', 'Mostrar', header_format)
            sheet.merge_range('I5:J5', summary, value_center_format)
            
            # Obtener datos optimizados
            total_lines = self._get_lines_optimized(company_id)
            
            # Obtener todos los product_ids para cargar costos en batch
            all_product_ids = []
            for lines in total_lines.values():
                all_product_ids.extend([l['product_id'] for l in lines])
            
            # Cargar costos en batch (una sola consulta)
            costs_cache = {}
            if all_product_ids:
                products = self.env['product.product'].with_company(company_id).browse(all_product_ids)
                costs_cache = {p.id: p.standard_price for p in products}
            
            if self.only_summary:
                self._write_summary_sheet(sheet, total_lines, costs_cache, 
                                         header_format, data_center, data_right_purple,
                                         grand_total_center, grand_total_right)
            else:
                self._write_detail_sheet(sheet, total_lines, costs_cache,
                                        header_format, data_center, data_right_purple,
                                        grand_total_center, grand_total_right)
        
        workbook.close()
        output.seek(0)
        
        # Guardar archivo
        xlsx_data = base64.encodebytes(output.read())
        
        attachment = self.env['ir.attachment'].create({
            'name': 'Reporte Valoración Inventario.xlsx',
            'type': 'binary',
            'datas': xlsx_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def _write_summary_sheet(self, sheet, total_lines, costs_cache,
                             header_format, data_center, data_right_purple,
                             grand_total_center, grand_total_right):
        """Escribir hoja en modo resumen."""
        sheet.set_column('A:A', 25)
        sheet.set_column('B:G', 20)
        
        row = 8
        sheet.write(row, 0, 'Categoría', header_format)
        sheet.write(row, 1, 'Inicial Total', header_format)
        sheet.write(row, 2, 'Entradas Total', header_format)
        sheet.write(row, 3, 'Salidas Total', header_format)
        sheet.write(row, 4, 'Ajustes Total', header_format)
        sheet.write(row, 5, 'Final Total', header_format)
        sheet.write(row, 6, 'Valor Total', header_format)
        
        row = 9
        grand_totals = {'begin': 0, 'in': 0, 'out': 0, 'adj': 0, 'end': 0, 'value': 0}
        
        for categ_id, lines in total_lines.items():
            cat_totals = {'begin': 0, 'in': 0, 'out': 0, 'adj': 0, 'end': 0, 'value': 0}
            categ_name = lines[0].get('categ_name') if lines else _('Sin Categoría')
            
            for line in lines:
                cost = costs_cache.get(line['product_id'], 0.0)
                ending = line.get('ending_qty', 0.0) or 0.0
                
                cat_totals['begin'] += line.get('begining_qty', 0.0) or 0.0
                cat_totals['in'] += line.get('product_qty_in', 0.0) or 0.0
                cat_totals['out'] += line.get('product_qty_out', 0.0) or 0.0
                cat_totals['adj'] += line.get('product_qty_adjustment', 0.0) or 0.0
                cat_totals['end'] += ending
                cat_totals['value'] += cost * ending
            
            sheet.write(row, 0, categ_name or _('Sin Categoría'), data_center)
            sheet.write(row, 1, cat_totals['begin'], data_right_purple)
            sheet.write(row, 2, cat_totals['in'], data_right_purple)
            sheet.write(row, 3, cat_totals['out'], data_right_purple)
            sheet.write(row, 4, cat_totals['adj'], data_right_purple)
            sheet.write(row, 5, cat_totals['end'], data_right_purple)
            sheet.write(row, 6, cat_totals['value'], data_right_purple)
            row += 1
            
            for key in grand_totals:
                grand_totals[key] += cat_totals[key]
        
        # Gran Total
        sheet.write(row, 0, 'Gran Total', grand_total_center)
        sheet.write(row, 1, grand_totals['begin'], grand_total_right)
        sheet.write(row, 2, grand_totals['in'], grand_total_right)
        sheet.write(row, 3, grand_totals['out'], grand_total_right)
        sheet.write(row, 4, grand_totals['adj'], grand_total_right)
        sheet.write(row, 5, grand_totals['end'], grand_total_right)
        sheet.write(row, 6, grand_totals['value'], grand_total_right)

    def _write_detail_sheet(self, sheet, total_lines, costs_cache,
                            header_format, data_center, data_right_purple,
                            grand_total_center, grand_total_right):
        """Escribir hoja en modo detalle."""
        sheet.set_column('A:A', 20)
        sheet.set_column('B:B', 40)
        sheet.set_column('C:C', 20)
        sheet.set_column('D:D', 20)
        sheet.set_column('E:K', 15)
        
        row = 8
        sheet.write(row, 0, 'Categoría', header_format)
        sheet.write(row, 1, 'Producto', header_format)
        sheet.write(row, 2, 'Código Barras', header_format)
        sheet.write(row, 3, 'Referencia', header_format)
        sheet.write(row, 4, 'Proveedor (LabHosPy)', header_format)
        sheet.write(row, 5, 'Inicial', header_format)
        sheet.write(row, 6, 'Entradas', header_format)
        sheet.write(row, 7, 'Salidas', header_format)
        sheet.write(row, 8, 'Ajustes', header_format)
        sheet.write(row, 9, 'Final', header_format)
        sheet.write(row, 10, 'Costo', header_format)
        sheet.write(row, 11, 'Valor Total', header_format)
        
        row = 9
        grand_totals = {'begin': 0, 'in': 0, 'out': 0, 'adj': 0, 'end': 0, 'value': 0}
        
        for categ_id, lines in total_lines.items():
            for line in lines:
                beginning = line.get('begining_qty', 0.0) or 0.0
                qty_in = line.get('product_qty_in', 0.0) or 0.0
                qty_out = line.get('product_qty_out', 0.0) or 0.0
                qty_adj = line.get('product_qty_adjustment', 0.0) or 0.0
                ending = line.get('ending_qty', 0.0) or 0.0
                
                # Los datos ya vienen filtrados de la consulta SQL
                cost = costs_cache.get(line['product_id'], 0.0)
                subtotal = cost * ending
                
                # Usar datos que vienen directamente de la consulta SQL
                categ_name = line.get('categ_name') or _('Sin Categoría')
                product_name = line.get('product_name') or ''
                barcode = line.get('barcode') or ''
                default_code = line.get('default_code') or ''
                
                sheet.write(row, 0, categ_name, data_center)
                sheet.write(row, 1, product_name, data_center)
                sheet.write(row, 2, barcode, data_center)
                sheet.write(row, 3, default_code, data_center)
                labhospy_supplier = line.get('labhospy_supplier_name') or ''
                sheet.write(row, 4, labhospy_supplier, data_center)
                sheet.write(row, 5, beginning, data_right_purple)
                sheet.write(row, 6, qty_in, data_right_purple)
                sheet.write(row, 7, qty_out, data_right_purple)
                sheet.write(row, 8, qty_adj, data_right_purple)
                sheet.write(row, 9, ending, data_right_purple)
                sheet.write(row, 10, cost, data_right_purple)
                sheet.write(row, 11, subtotal, data_right_purple)
                row += 1
                
                grand_totals['begin'] += beginning
                grand_totals['in'] += qty_in
                grand_totals['out'] += qty_out
                grand_totals['adj'] += qty_adj
                grand_totals['end'] += ending
                grand_totals['value'] += subtotal
        
        # Gran Total
        sheet.write(row, 3, 'Gran Total', grand_total_center)
        sheet.write(row, 4, '', grand_total_center)
        sheet.write(row, 5, grand_totals['begin'], grand_total_right)
        sheet.write(row, 6, grand_totals['in'], grand_total_right)
        sheet.write(row, 7, grand_totals['out'], grand_total_right)
        sheet.write(row, 8, grand_totals['adj'], grand_total_right)
        sheet.write(row, 9, grand_totals['end'], grand_total_right)
        sheet.write(row, 10, '-', grand_total_center)
        sheet.write(row, 11, grand_totals['value'], grand_total_right)
