# -*- coding: utf-8 -*-
"""
Helper centralizado para el reporte de valoración de inventario.
Elimina código duplicado y optimiza consultas SQL.
"""

import pytz
from datetime import datetime
from itertools import groupby

from odoo import _, api
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class StockValuationHelper:
    """Clase helper para compartir lógica entre wizard y report."""

    @staticmethod
    def convert_to_utc(env, date_str, end_of_day=False):
        """Convertir fecha local a UTC considerando zona horaria del usuario."""
        if isinstance(date_str, datetime):
            date_str = date_str.strftime(DEFAULT_SERVER_DATE_FORMAT)
        
        time_suffix = ' 23:59:59' if end_of_day else ' 00:00:00'
        user_datetime_str = str(date_str) + time_suffix
        user_datetime = datetime.strptime(user_datetime_str, DEFAULT_SERVER_DATETIME_FORMAT)
        
        tz_name = env.context.get('tz') or env.user.tz or 'UTC'
        try:
            user_tz = pytz.timezone(tz_name)
            utc_tz = pytz.timezone('UTC')
            local_dt = user_tz.localize(user_datetime, is_dst=False)
            utc_dt = local_dt.astimezone(utc_tz)
            return utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        except Exception:
            return user_datetime_str

    @staticmethod
    def find_warehouses(env, company_id):
        """Encontrar almacenes de una compañía."""
        return env['stock.warehouse'].search([('company_id', '=', company_id)]).ids

    @staticmethod
    def find_locations(env, warehouse_ids):
        """Encontrar ubicaciones internas de almacenes."""
        if not warehouse_ids:
            return []
        
        Warehouse = env['stock.warehouse']
        Location = env['stock.location']
        
        view_location_ids = Warehouse.browse(warehouse_ids).mapped('view_location_id').ids
        if not view_location_ids:
            return []
        
        return Location.search([
            ('location_id', 'child_of', view_location_ids),
            ('usage', '=', 'internal')
        ]).ids

    @staticmethod
    def get_movement_data_optimized(cr, start_date, end_date, locations, 
                                     filter_categ_ids=None, only_with_movement=True,
                                     filter_supplier_ids=None):
        """
        Obtener datos de movimiento con consulta SQL optimizada.
        
        Usa CTE para combinar inventario inicial y movimientos en una sola consulta.
        Solo trae productos que tienen movimiento (mucho más eficiente).
        
        Args:
            cr: cursor de la base de datos
            start_date: fecha inicio en UTC
            end_date: fecha fin en UTC
            locations: lista de IDs de ubicaciones
            filter_categ_ids: lista de IDs de categorías (opcional)
            only_with_movement: si True, solo trae productos con movimiento
            filter_supplier_ids: lista de IDs gn.labhospy.supplier (opcional)
        
        Returns:
            dict: datos agrupados por categoría
        """
        if not locations:
            return {}
        
        locations_tuple = tuple(locations)
        
        # Consulta optimizada con CTE - Una sola consulta que hace todo
        query = '''
            WITH product_movements AS (
                SELECT 
                    smline.product_id,
                    -- Inventario inicial (antes del período)
                    COALESCE(SUM(
                        CASE WHEN smline.date < %(start_date)s THEN
                            CASE 
                                WHEN smline.location_dest_id IN %(locations)s THEN smline.quantity
                                WHEN smline.location_id IN %(locations)s THEN -smline.quantity
                                ELSE 0 
                            END
                        ELSE 0 END
                    ), 0.0) AS begining_qty,
                    -- Entradas en período (excluye ajustes de inventario)
                    COALESCE(SUM(
                        CASE WHEN smline.date >= %(start_date)s AND smline.date <= %(end_date)s 
                             AND destl.usage = 'internal' 
                             AND smline.location_dest_id IN %(locations)s 
                             AND sourcel.usage NOT IN ('inventory', 'internal')
                        THEN smline.quantity ELSE 0 END
                    ), 0.0) AS product_qty_in,
                    -- Salidas en período (excluye ajustes de inventario)
                    COALESCE(SUM(
                        CASE WHEN smline.date >= %(start_date)s AND smline.date <= %(end_date)s
                             AND sourcel.usage = 'internal' 
                             AND smline.location_id IN %(locations)s
                             AND destl.usage NOT IN ('inventory', 'internal')
                        THEN -smline.quantity ELSE 0 END
                    ), 0.0) AS product_qty_out,
                    -- Ajustes de inventario en período
                    COALESCE(SUM(
                        CASE WHEN smline.date >= %(start_date)s AND smline.date <= %(end_date)s THEN
                            CASE 
                                WHEN sourcel.usage = 'inventory' AND smline.location_dest_id IN %(locations)s 
                                THEN smline.quantity
                                WHEN destl.usage = 'inventory' AND smline.location_id IN %(locations)s 
                                THEN -smline.quantity
                                ELSE 0 
                            END
                        ELSE 0 END
                    ), 0.0) AS product_qty_adjustment,
                    -- Transferencias internas en período (para referencia)
                    COALESCE(SUM(
                        CASE WHEN smline.date >= %(start_date)s AND smline.date <= %(end_date)s
                             AND sourcel.usage = 'internal' AND destl.usage = 'internal'
                             AND smline.location_id IN %(locations)s
                             AND smline.location_dest_id IN %(locations)s
                        THEN smline.quantity ELSE 0 END
                    ), 0.0) AS internal_transfers
                FROM stock_move_line smline
                JOIN stock_location sourcel ON smline.location_id = sourcel.id
                JOIN stock_location destl ON smline.location_dest_id = destl.id
                WHERE smline.state = 'done'
                  AND smline.location_id != smline.location_dest_id
                  AND (smline.location_id IN %(locations)s OR smline.location_dest_id IN %(locations)s)
                GROUP BY smline.product_id
            )
            SELECT 
                pm.product_id,
                pt.categ_id,
                pc.complete_name AS categ_name,
                pp.default_code,
                pp.barcode,
                COALESCE(
                    pt.name->>'es_SV', 
                    pt.name->>'en_US', 
                    pt.name->>'es_ES',
                    pt.name->>'es_GT',
                    (SELECT value FROM jsonb_each_text(pt.name) LIMIT 1)
                ) AS product_name,
                gls.name AS labhospy_supplier_name,
                pm.begining_qty,
                pm.product_qty_in,
                pm.product_qty_out,
                pm.product_qty_adjustment,
                (pm.begining_qty + pm.product_qty_in + pm.product_qty_out + pm.product_qty_adjustment) AS ending_qty
            FROM product_movements pm
            JOIN product_product pp ON pm.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN product_category pc ON pt.categ_id = pc.id
            LEFT JOIN gn_labhospy_supplier gls ON pt.gn_labhospy_supplier_id = gls.id
            WHERE pp.active = true
        '''
        
        # Agregar filtro de solo con movimiento
        if only_with_movement:
            query += '''
              AND (
                  pm.begining_qty != 0 
                  OR pm.product_qty_in != 0 
                  OR pm.product_qty_out != 0 
                  OR pm.product_qty_adjustment != 0
                  OR (pm.begining_qty + pm.product_qty_in + pm.product_qty_out + pm.product_qty_adjustment) != 0
              )
            '''
        
        # Agregar filtro de categorías
        if filter_categ_ids:
            query += ' AND pt.categ_id IN %(categ_ids)s'
        
        # Filtro por proveedor LabHosPy (plantilla de producto)
        if filter_supplier_ids:
            query += ' AND pt.gn_labhospy_supplier_id IN %(supplier_ids)s'
        
        query += ' ORDER BY pc.complete_name NULLS FIRST, pt.name'
        
        params = {
            'start_date': start_date,
            'end_date': end_date,
            'locations': locations_tuple,
        }
        if filter_categ_ids:
            params['categ_ids'] = tuple(filter_categ_ids)
        if filter_supplier_ids:
            params['supplier_ids'] = tuple(filter_supplier_ids)
        
        cr.execute(query, params)
        records = cr.dictfetchall()
        
        # Agrupar por categoría
        def get_categ_key(r):
            return r.get('categ_id') or 0
        
        sorted_records = sorted(records, key=get_categ_key)
        records_by_category = {}
        for categ_id, items in groupby(sorted_records, key=get_categ_key):
            records_by_category[categ_id] = list(items)
        
        return records_by_category

    @staticmethod
    def get_products_costs_batch(cr, product_ids, company_id):
        """
        Obtener costos de múltiples productos en una sola consulta.
        
        Args:
            cr: cursor de la base de datos
            product_ids: lista de IDs de productos
            company_id: ID de la compañía
        
        Returns:
            dict: {product_id: cost}
        """
        if not product_ids:
            return {}
        
        # Consulta optimizada para obtener standard_price de ir.property
        cr.execute('''
            SELECT 
                pp.id AS product_id,
                COALESCE(
                    (SELECT NULLIF(split_part(value_reference, ',', 2), '')::float
                     FROM ir_property 
                     WHERE name = 'standard_price' 
                       AND res_id = 'product.product,' || pp.id::text
                       AND (company_id = %(company_id)s OR company_id IS NULL)
                     ORDER BY company_id NULLS LAST
                     LIMIT 1),
                    pt.list_price,
                    0.0
                ) AS cost
            FROM product_product pp
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            WHERE pp.id IN %(product_ids)s
        ''', {'product_ids': tuple(product_ids), 'company_id': company_id})
        
        return {r['product_id']: r['cost'] or 0.0 for r in cr.dictfetchall()}

    @staticmethod
    def get_categ_name(env, categ_id, categ_cache=None):
        """Obtener nombre de categoría con cache."""
        if not categ_id:
            return _('Sin Categoría')
        
        if categ_cache and categ_id in categ_cache:
            return categ_cache[categ_id]
        
        categ = env['product.category'].browse(categ_id)
        name = categ.complete_name if categ else _('Sin Categoría')
        
        if categ_cache is not None:
            categ_cache[categ_id] = name
        
        return name

    @staticmethod
    def get_warehouses_name(env, warehouse_ids, company_id):
        """Obtener nombres de almacenes."""
        if not warehouse_ids:
            return _('TODOS')
        
        warehouses = env['stock.warehouse'].search([
            ('id', 'in', warehouse_ids),
            ('company_id', '=', company_id)
        ])
        return ", ".join(warehouses.mapped('name')) if warehouses else '-'

    @staticmethod
    def get_valid_companies(env, company_ids):
        """Obtener compañías válidas con almacenes."""
        Company = env['res.company']
        Warehouse = env['stock.warehouse']
        
        if not company_ids:
            company_ids = Company.search([]).ids
        
        return [c for c in company_ids if Warehouse.search([('company_id', '=', c)], limit=1)]

    @staticmethod
    def value_existed(beginning, qty_in, qty_out, qty_adj, ending):
        """Verificar si hay valores."""
        return beginning or qty_in or qty_out or qty_adj or ending
