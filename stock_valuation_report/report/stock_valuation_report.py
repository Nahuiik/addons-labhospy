# -*- coding: utf-8 -*-
"""
Reporte PDF optimizado para valoración de inventario.
Usa el helper centralizado para evitar código duplicado.
"""

from odoo import models, api, _
from odoo.exceptions import UserError

from ..models.stock_valuation_helper import StockValuationHelper


class StockValuationReport(models.AbstractModel):
    _name = 'report.stock_valuation_report.stock_valuation_report_template'
    _description = 'Reporte de Valoración de Inventario'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data.get('form'):
            raise UserError(_("Falta el contenido del formulario, este reporte no puede ser impreso."))
        
        return {
            'doc_ids': self._ids,
            'docs': self,
            'data': data,
            'get_warehouse_name': self._get_warehouse_name,
            'get_warehouses_block': self._get_warehouses_block,
            'get_company': self._get_company,
            'get_product_name': self._get_product_name,
            'get_product_detail': self._get_product_detail,
            'get_categ': self._get_categ,
            'get_lines': self._get_lines,
            'get_cost': self._get_cost,
            'get_subtotal_cost': self._get_subtotal_cost
        }

    def _get_warehouses_block(self, warehouse_ids, company_id):
        """Obtener nombres de almacenes."""
        return StockValuationHelper.get_warehouses_name(self.env, warehouse_ids, company_id)

    def _get_company(self, company_ids):
        """Obtener información de compañías."""
        Company = self.env['res.company']
        
        valid_company_ids = StockValuationHelper.get_valid_companies(self.env, company_ids)
        
        return Company.browse(valid_company_ids).read(['name', 'currency_id'])

    def _get_warehouse_name(self, warehouse_ids):
        """Obtener nombres de almacenes."""
        Warehouse = self.env['stock.warehouse']
        if not warehouse_ids:
            warehouse_ids = Warehouse.search([]).ids
        
        warehouses = Warehouse.browse(warehouse_ids)
        return ', '.join(warehouses.mapped('name'))

    def _get_cost(self, company_id, product_id, inventory_date, ending_inventory):
        """Obtener costo del producto."""
        if not product_id:
            return 0.0
        product = self.env['product.product'].with_company(company_id).browse(product_id)
        return product.standard_price if product else 0.0

    def _get_subtotal_cost(self, cost, ending_inv, current_record):
        """Calcular costo subtotal."""
        subtotal_cost = round((cost or 0.0) * (ending_inv or 0.0), 2)
        if isinstance(current_record, dict):
            current_record['subtotal_cost'] = subtotal_cost
        return subtotal_cost

    def _get_categ(self, categ_id):
        """Obtener nombre de categoría."""
        return StockValuationHelper.get_categ_name(self.env, categ_id)

    def _get_product_name(self, product_id):
        """Obtener nombre del producto."""
        if not product_id:
            return ''
        product = self.env['product.product'].browse(product_id)
        return product.display_name if product else ''

    def _get_product_detail(self, product_id):
        """Obtener detalles del producto: nombre, código de barras, código por defecto."""
        if not product_id:
            return {'name': '', 'barcode': '', 'default_code': ''}
        
        product = self.env['product.product'].browse(product_id)
        if not product:
            return {'name': '', 'barcode': '', 'default_code': ''}
        
        # Construir nombre con variantes
        variant = ", ".join([v.name for v in product.product_template_attribute_value_ids])
        product_name = f"{product.name} ({variant})" if variant else product.name
        
        return {
            'name': product_name or '',
            'barcode': product.barcode or '',
            'default_code': product.default_code or ''
        }

    def _get_lines(self, data, company_id):
        """
        Obtener líneas del reporte agrupadas por categoría.
        Usa la consulta optimizada del helper.
        """
        form = data.get('form', {})
        
        start_date = StockValuationHelper.convert_to_utc(self.env, form['start_date'], end_of_day=False)
        end_date = StockValuationHelper.convert_to_utc(self.env, form['end_date'], end_of_day=True)
        
        warehouse_ids = form.get('warehouse_ids') or []
        filter_product_categ_ids = form.get('filter_product_categ_ids') or []
        filter_gn_labhospy_supplier_ids = form.get('filter_gn_labhospy_supplier_ids') or []
        only_with_movement = form.get('only_with_movement', True)
        
        if not warehouse_ids:
            warehouse_ids = StockValuationHelper.find_warehouses(self.env, company_id)
        
        # Obtener ubicaciones
        location_id = form.get('location_id')
        if location_id:
            locations = [location_id]
        else:
            locations = StockValuationHelper.find_locations(self.env, warehouse_ids)
        
        if not locations:
            return {}
        
        # Usar consulta optimizada
        return StockValuationHelper.get_movement_data_optimized(
            self._cr,
            start_date,
            end_date,
            locations,
            filter_product_categ_ids if filter_product_categ_ids else None,
            only_with_movement,
            filter_gn_labhospy_supplier_ids if filter_gn_labhospy_supplier_ids else None,
        )
