# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Módulo optimizado para reporte de movimientos de inventario.
Mejoras implementadas:
- Consulta SQL optimizada con CTE
- Filtrado en SQL con HAVING (no en Python)
- Pre-carga de datos en batch
- Eliminación de consultas N+1
"""

import json
import datetime
import io
import pytz
import logging

from markupsafe import Markup
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools import date_utils, SQL, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError, ValidationError

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

_logger = logging.getLogger(__name__)


class InventoryMovementReport(models.AbstractModel):
    _name = 'inventory.movement.report'
    _description = 'Inventory Movement Report'

    # ==================== MÉTODOS DE BOTONES Y NOMBRES ====================
    
    def get_reports_buttons(self):
        return [{'name': _('Print Preview'), 'action': 'print_pdf'}, {'name': _('Export (XLSX)'), 'action': 'print_xlsx'}]

    def _get_report_name(self):
        return _('Inventory Movement Report')

    def get_report_filename(self, options):
        """The name that will be used for the file when downloading pdf,xlsx,..."""
        return self._get_report_name().lower().replace(' ', '_')

    def _get_report_super_columns(self, options):
        columns = [
            {'string': _('Internal Reference')},
            {'string': _('Product')},
            {'string': _('Vendor (LabHosPy)')},
            {'string': _('Opening Qty')},
            {'string': _('Qty In')},
            {'string': _('Qty Out')},
            {'string': _('Closing Qty')},
            {'string': _('Opening Value')},
            {'string': _('Value In')},
            {'string': _('Value Out')},
            {'string': _('Closing Value')},
        ]
        return {'columns': columns, 'x_offset': 0, 'merge': 0}

    def _get_report_qweb_labels(self):
        """Etiquetas para plantillas QWeb (msgid exportables a i18n)."""
        return {
            'company': _('Company'),
            'categories': _('Categories'),
            'warehouses': _('Warehouses'),
            'locations': _('Locations'),
            'period_as_of': _('Period As of'),
            'to': _('To'),
            'no_data': _('No inventory data found! Modify your search criteria.'),
            'total': _('Total'),
            'internal_reference': _('Internal Reference'),
            'product': _('Product'),
            'labhospy_supplier': _('Vendor (LabHosPy)'),
            'opening_qty': _('Opening Qty'),
            'qty_in': _('Qty In'),
            'qty_out': _('Qty Out'),
            'closing_qty': _('Closing Qty'),
            'opening_value': _('Opening Value'),
            'value_in': _('Value In'),
            'value_out': _('Value Out'),
            'closing_value': _('Closing Value'),
        }

    def _report_display_fields(self):
        return [
            ('qty', 'opening_qty'),
            ('in_qty', 'incoming_qty'),
            ('out_qty', 'outgoing_qty'),
            ('calc_close_qty', 'virtual_available'),
            ('value', 'stock_value'),
            ('in_values', 'incoming_value'),
            ('out_values', 'outgoing_value'),
            ('calc_value_close', 'virtual_value'),
        ]

    def _get_header_values(self, values):
        return {
            f"total_{field}": sum(v.get(field, 0.0) for v in values)
            for _, field in self._report_display_fields()
        }

    # ==================== MÉTODOS DE CONVERSIÓN DE FECHAS ====================
    
    def _convert_to_utc(self, date_str, end_of_day=False):
        """
        Convierte una fecha (string o date) a datetime UTC considerando la zona horaria del usuario.
        """
        if isinstance(date_str, (datetime.date, datetime.datetime)):
            date_str = date_str.strftime('%Y-%m-%d')
        
        time_suffix = ' 23:59:59' if end_of_day else ' 00:00:00'
        user_datetime_str = date_str + time_suffix
        user_datetime = datetime.datetime.strptime(user_datetime_str, DEFAULT_SERVER_DATETIME_FORMAT)
        
        tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        try:
            user_tz = pytz.timezone(tz_name)
            utc_tz = pytz.timezone('UTC')
            local_dt = user_tz.localize(user_datetime, is_dst=False)
            utc_dt = local_dt.astimezone(utc_tz)
            return utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        except Exception:
            return user_datetime_str

    def _get_date_range_dates(self, search_filters, display_for_qweb=False):
        today = fields.Date.context_today(self)
        date_from = date_to = today
        options_filter = search_filters.get('date', {}).get('filter', 'today')

        if options_filter == 'custom':
            date_from = fields.Date.from_string(search_filters['date']['date_from'])
            date_to = fields.Date.from_string(search_filters['date']['date_to'])
        elif options_filter == 'week':
            date_from = date_utils.start_of(today, 'week')
            date_to = date_utils.end_of(today, 'week')
        elif options_filter == 'month':
            date_from, date_to = date_utils.get_month(today)

        if display_for_qweb:
            date_from, date_to = map(fields.Date.from_string, (date_from, date_to))

        return {'date_from': date_from, 'date_to': date_to}

    # ==================== MÉTODOS DE UBICACIONES ====================
    
    def _find_internal_locations(self, search_filters):
        """Encuentra todas las ubicaciones internas basadas en los filtros."""
        Location = self.env['stock.location']
        Warehouse = self.env['stock.warehouse']
        
        company_id = search_filters.get('company_id') or self.env.company.id
        warehouses = search_filters.get('warehouses') or []
        locations = search_filters.get('locations') or []
        
        if locations:
            return locations
        
        if warehouses:
            warehouse_recs = Warehouse.browse(warehouses)
        else:
            warehouse_recs = Warehouse.search([('company_id', '=', company_id)])
        
        if not warehouse_recs:
            return Location.search([('usage', '=', 'internal')]).ids
        
        view_location_ids = warehouse_recs.mapped('view_location_id').ids
        return Location.search([
            ('location_id', 'child_of', view_location_ids),
            ('usage', '=', 'internal')
        ]).ids

    def _get_correspond_company(self, company_id=False):
        if company_id and company_id in self.env.companies.ids:
            return company_id
        return self.env.company.id

    def _sql_filter_only_with_movements(self, search_filters):
        """Fragmento SQL: excluir productos sin actividad en el periodo (saldo y movimientos en 0)."""
        if not search_filters.get('only_with_movements', True):
            return ''
        return """
                  AND (
                      pm.beginning_qty != 0
                      OR pm.qty_in != 0
                      OR pm.qty_out != 0
                      OR pm.qty_adjustment != 0
                      OR (pm.beginning_qty + pm.qty_in + pm.qty_out + pm.qty_adjustment) != 0
                  )"""

    # ==================== CONSULTA SQL OPTIMIZADA ====================
    
    def _get_inventory_movement_data_optimized(self, search_filters, locations, start_date, end_date, 
                                                limit=0, offset=0, count_only=False, company_id=None):
        """
        Obtiene los datos de movimiento usando SQL optimizado con CTE.
        
        Mejoras:
        - Una sola consulta CTE que combina inventario inicial y movimientos
        - Filtrado en SQL con HAVING (no en Python)
        - Incluye datos de producto directamente
        - Soporte para paginación en SQL
        """
        if not locations:
            return [] if not count_only else 0
        
        locations_tuple = tuple(locations)
        
        # Construir filtros de producto/categoría
        product_filters = []
        params = {
            'locations': locations_tuple,
            'start_date': start_date,
            'end_date': end_date,
        }
        
        if search_filters.get('products'):
            product_ids = [int(p) for p in search_filters['products']]
            product_filters.append("pp.id IN %(product_ids)s")
            params['product_ids'] = tuple(product_ids)
        
        if search_filters.get('categories'):
            cat_ids = search_filters['categories']
            # Obtener categorías hijas con CTE recursivo
            self.env.cr.execute("""
                WITH RECURSIVE cat_tree AS (
                    SELECT id FROM product_category WHERE id IN %s
                    UNION ALL
                    SELECT pc.id FROM product_category pc
                    JOIN cat_tree ct ON pc.parent_id = ct.id
                )
                SELECT ARRAY_AGG(id) FROM cat_tree
            """, (tuple(cat_ids),))
            result = self.env.cr.fetchone()
            if result and result[0]:
                product_filters.append("pt.categ_id IN %(categ_ids)s")
                params['categ_ids'] = tuple(result[0])
        
        if search_filters.get('search'):
            product_filters.append("(pt.name::text ILIKE %(search)s OR pp.default_code ILIKE %(search)s)")
            params['search'] = f"%{search_filters['search']}%"
        
        product_filter_sql = " AND ".join(product_filters) if product_filters else "TRUE"
        movement_sql = self._sql_filter_only_with_movements(search_filters)

        # Consulta principal optimizada con CTE
        query = """
            WITH product_movements AS (
                SELECT 
                    smline.product_id,
                    -- Inventario inicial (antes del período)
                    -- IMPORTANTE: Incluye TODOS los movimientos antes del período, incluyendo ajustes de inventario
                    COALESCE(SUM(
                        CASE WHEN smline.date < %(start_date)s THEN
                            CASE 
                                -- Entrada a ubicación interna (incluye ajustes de inventario)
                                WHEN smline.location_dest_id IN %(locations)s THEN smline.quantity
                                -- Salida desde ubicación interna (incluye ajustes de inventario)
                                WHEN smline.location_id IN %(locations)s THEN -smline.quantity
                                ELSE 0 
                            END
                        ELSE 0 END
                    ), 0.0) AS beginning_qty,
                    -- Entradas en período (excluye ajustes)
                    COALESCE(SUM(
                        CASE WHEN smline.date >= %(start_date)s AND smline.date <= %(end_date)s 
                             AND destl.usage = 'internal' 
                             AND smline.location_dest_id IN %(locations)s
                             AND sourcel.usage NOT IN ('inventory', 'internal')
                        THEN smline.quantity ELSE 0 END
                    ), 0.0) AS qty_in,
                    -- Salidas en período (excluye ajustes)
                    COALESCE(SUM(
                        CASE WHEN smline.date >= %(start_date)s AND smline.date <= %(end_date)s
                             AND sourcel.usage = 'internal' 
                             AND smline.location_id IN %(locations)s
                             AND destl.usage NOT IN ('inventory', 'internal')
                        THEN smline.quantity ELSE 0 END
                    ), 0.0) AS qty_out,
                    -- Ajustes de inventario
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
                    ), 0.0) AS qty_adjustment
                FROM stock_move_line smline
                JOIN stock_location sourcel ON smline.location_id = sourcel.id
                JOIN stock_location destl ON smline.location_dest_id = destl.id
                WHERE smline.state = 'done'
                  AND smline.location_id != smline.location_dest_id
                  AND (smline.location_id IN %(locations)s OR smline.location_dest_id IN %(locations)s)
                GROUP BY smline.product_id
            )
        """
        
        if count_only:
            query += """
                SELECT COUNT(*) 
                FROM product_movements pm
                JOIN product_product pp ON pm.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE pp.active = true 
                  AND {product_filter_sql}
                  {movement_sql}
            """.format(product_filter_sql=product_filter_sql, movement_sql=movement_sql)
            
            self.env.cr.execute(query, params)
            result = self.env.cr.fetchone()
            return result[0] if result else 0
        
        # Consulta completa con datos de producto (sin standard_price que es campo property)
        query += """
            SELECT 
                pm.product_id,
                pp.default_code AS product_reference,
                COALESCE(
                    pt.name->>'es_SV', 
                    pt.name->>'en_US', 
                    pt.name->>'es_ES',
                    pt.name->>'es_GT',
                    (SELECT value FROM jsonb_each_text(pt.name) LIMIT 1)
                ) AS product_name,
                gls.name AS labhospy_supplier_name,
                pm.beginning_qty,
                pm.qty_in,
                pm.qty_out,
                pm.qty_adjustment,
                -- Cálculo consistente con stock_valuation_report: qty_out ya viene negativo
                (pm.beginning_qty + pm.qty_in + pm.qty_out + pm.qty_adjustment) AS ending_qty,
                COALESCE(pt.list_price, 0.0) AS list_price
            FROM product_movements pm
            JOIN product_product pp ON pm.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN gn_labhospy_supplier gls ON pt.gn_labhospy_supplier_id = gls.id
            WHERE pp.active = true 
              AND {product_filter_sql}
              {movement_sql}
            ORDER BY pt.name, pp.default_code
        """.format(product_filter_sql=product_filter_sql, movement_sql=movement_sql)
        
        if limit:
            query += " LIMIT %(limit)s OFFSET %(offset)s"
            params['limit'] = limit
            params['offset'] = offset
        
        # JUSTIFICACIÓN: SQL directo necesario para consulta optimizada con CTE que mejora
        # significativamente el rendimiento comparado con ORM. Consulta completamente
        # parametrizada para prevenir SQL injection.
        self.env.cr.execute(query, params)
        rows = self.env.cr.dictfetchall()
        
        if not rows:
            return []
        
        # Obtener costos en batch usando ORM (standard_price es campo property)
        # Usar with_company para obtener el costo correcto según la compañía
        # IMPORTANTE: Usar el mismo método que stock_valuation_report para consistencia
        product_ids = [row['product_id'] for row in rows]
        if company_id:
            products = self.env['product.product'].with_company(company_id).browse(product_ids)
        else:
            products = self.env['product.product'].browse(product_ids)
        # Obtener standard_price directamente (igual que stock_valuation_report)
        costs_cache = {p.id: (p.standard_price if p.standard_price else 0.0) for p in products}
        
        # Procesar resultados
        results = []
        for row in rows:
            rounding = 0.01  # Redondeo por defecto
            cost = costs_cache.get(row['product_id'], row['list_price'] or 0.0)
            
            opening_qty = float_round(row['beginning_qty'] or 0.0, precision_rounding=rounding)
            # Incluir ajustes de inventario en incoming_qty para que sean visibles en el reporte
            qty_in_raw = row['qty_in'] or 0.0
            qty_adjustment_raw = row['qty_adjustment'] or 0.0
            # Sumar ajustes positivos a las entradas (los ajustes negativos ya están en qty_out)
            incoming_qty = float_round(qty_in_raw + max(0, qty_adjustment_raw), precision_rounding=rounding)
            # qty_out ahora viene negativo (consistente con stock_valuation_report)
            # Incluir ajustes negativos en las salidas
            qty_out_raw = (row['qty_out'] or 0.0) + min(0, qty_adjustment_raw)
            outgoing_qty = float_round(abs(qty_out_raw), precision_rounding=rounding)
            virtual_qty = float_round(row['ending_qty'] or 0.0, precision_rounding=rounding)
            
            results.append({
                'id': row['product_id'],
                'product_name': row['product_name'] or '',
                'product_reference': row['product_reference'] or '',
                'labhospy_supplier': row.get('labhospy_supplier_name') or '',
                'opening_qty': opening_qty,
                'incoming_qty': incoming_qty,  # Incluye ajustes positivos
                'outgoing_qty': outgoing_qty,  # Valor absoluto para visualización, incluye ajustes negativos
                'virtual_available': virtual_qty,
                'stock_value': float_round(opening_qty * cost, precision_digits=2),
                # Incluir valor de ajustes positivos en incoming_value
                'incoming_value': float_round((qty_in_raw + max(0, qty_adjustment_raw)) * cost, precision_digits=2),
                # outgoing_value debe ser negativo (reducción de inventario), incluye ajustes negativos
                'outgoing_value': float_round(qty_out_raw * cost, precision_digits=2),
                'virtual_value': float_round(virtual_qty * cost, precision_digits=2),
            })
        
        return results

    def _count_products_with_movement(self, search_filters):
        """Cuenta productos con movimiento usando la consulta optimizada."""
        dates = self._get_date_range_dates(search_filters) or {}
        date_from = dates.get('date_from')
        date_to = dates.get('date_to')
        
        start_date = self._convert_to_utc(date_from, end_of_day=False) if date_from else None
        end_date = self._convert_to_utc(date_to, end_of_day=True) if date_to else None
        
        if not start_date or not end_date:
            return 0
        
        locations = self._find_internal_locations(search_filters)
        if not locations:
            return 0
        
        company_id = search_filters.get('company_id') or self.env.company.id
        
        return self._get_inventory_movement_data_optimized(
            search_filters, locations, start_date, end_date, count_only=True, company_id=company_id
        )

    def _get_aggregate_totals(self, search_filters):
        """
        Calcula los totales agregados de TODOS los productos sin paginación.
        Usa una consulta SQL optimizada que incluye el costo desde el campo JSONB
        standard_price de product_product para calcular los valores monetarios.
        
        JUSTIFICACIÓN: SQL directo necesario para calcular totales eficientemente
        sin cargar todos los productos en memoria. Consulta completamente
        parametrizada para prevenir SQL injection.
        """
        dates = self._get_date_range_dates(search_filters) or {}
        date_from = dates.get('date_from')
        date_to = dates.get('date_to')
        
        start_date = self._convert_to_utc(date_from, end_of_day=False) if date_from else None
        end_date = self._convert_to_utc(date_to, end_of_day=True) if date_to else None
        
        if not start_date or not end_date:
            return self._empty_totals()
        
        locations = self._find_internal_locations(search_filters)
        if not locations:
            return self._empty_totals()
        
        locations_tuple = tuple(locations)
        company_id = search_filters.get('company_id') or self.env.company.id
        
        # Construir filtros de producto/categoría (misma lógica que la consulta principal)
        product_filters = []
        params = {
            'locations': locations_tuple,
            'start_date': start_date,
            'end_date': end_date,
            'company_id': str(company_id),
        }
        
        if search_filters.get('products'):
            product_ids = [int(p) for p in search_filters['products']]
            product_filters.append("pp.id IN %(product_ids)s")
            params['product_ids'] = tuple(product_ids)
        
        if search_filters.get('categories'):
            cat_ids = search_filters['categories']
            self.env.cr.execute("""
                WITH RECURSIVE cat_tree AS (
                    SELECT id FROM product_category WHERE id IN %s
                    UNION ALL
                    SELECT pc.id FROM product_category pc
                    JOIN cat_tree ct ON pc.parent_id = ct.id
                )
                SELECT ARRAY_AGG(id) FROM cat_tree
            """, (tuple(cat_ids),))
            result = self.env.cr.fetchone()
            if result and result[0]:
                product_filters.append("pt.categ_id IN %(categ_ids)s")
                params['categ_ids'] = tuple(result[0])
        
        if search_filters.get('search'):
            product_filters.append("(pt.name::text ILIKE %(search)s OR pp.default_code ILIKE %(search)s)")
            params['search'] = f"%{search_filters['search']}%"
        
        product_filter_sql = " AND ".join(product_filters) if product_filters else "TRUE"
        movement_sql = self._sql_filter_only_with_movements(search_filters)

        query = """
            WITH product_movements AS (
                SELECT 
                    smline.product_id,
                    COALESCE(SUM(
                        CASE WHEN smline.date < %(start_date)s THEN
                            CASE 
                                WHEN smline.location_dest_id IN %(locations)s THEN smline.quantity
                                WHEN smline.location_id IN %(locations)s THEN -smline.quantity
                                ELSE 0 
                            END
                        ELSE 0 END
                    ), 0.0) AS beginning_qty,
                    COALESCE(SUM(
                        CASE WHEN smline.date >= %(start_date)s AND smline.date <= %(end_date)s 
                             AND destl.usage = 'internal' 
                             AND smline.location_dest_id IN %(locations)s
                             AND sourcel.usage NOT IN ('inventory', 'internal')
                        THEN smline.quantity ELSE 0 END
                    ), 0.0) AS qty_in,
                    COALESCE(SUM(
                        CASE WHEN smline.date >= %(start_date)s AND smline.date <= %(end_date)s
                             AND sourcel.usage = 'internal' 
                             AND smline.location_id IN %(locations)s
                             AND destl.usage NOT IN ('inventory', 'internal')
                        THEN smline.quantity ELSE 0 END
                    ), 0.0) AS qty_out,
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
                    ), 0.0) AS qty_adjustment
                FROM stock_move_line smline
                JOIN stock_location sourcel ON smline.location_id = sourcel.id
                JOIN stock_location destl ON smline.location_dest_id = destl.id
                WHERE smline.state = 'done'
                  AND smline.location_id != smline.location_dest_id
                  AND (smline.location_id IN %(locations)s OR smline.location_dest_id IN %(locations)s)
                GROUP BY smline.product_id
            )
            SELECT 
                COALESCE(SUM(beginning_qty), 0.0) AS total_opening_qty,
                COALESCE(SUM(qty_in + GREATEST(qty_adjustment, 0)), 0.0) AS total_incoming_qty,
                COALESCE(SUM(qty_out + ABS(LEAST(qty_adjustment, 0))), 0.0) AS total_outgoing_qty,
                COALESCE(SUM(beginning_qty + qty_in - qty_out + qty_adjustment), 0.0) AS total_virtual_available,
                COALESCE(SUM(beginning_qty * cost), 0.0) AS total_stock_value,
                COALESCE(SUM((qty_in + GREATEST(qty_adjustment, 0)) * cost), 0.0) AS total_incoming_value,
                COALESCE(SUM((qty_out + ABS(LEAST(qty_adjustment, 0))) * cost), 0.0) AS total_outgoing_value,
                COALESCE(SUM((beginning_qty + qty_in - qty_out + qty_adjustment) * cost), 0.0) AS total_virtual_value
            FROM (
                SELECT 
                    pm.*,
                    COALESCE(
                        (pp.standard_price->>%(company_id)s)::float,
                        pt.list_price::float,
                        0.0
                    ) AS cost
                FROM product_movements pm
                JOIN product_product pp ON pm.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE pp.active = true 
                  AND {product_filter_sql}
                  {movement_sql}
            ) sub
        """.format(product_filter_sql=product_filter_sql, movement_sql=movement_sql)
        
        self.env.cr.execute(query, params)
        row = self.env.cr.dictfetchone()
        
        if not row:
            return self._empty_totals()
        
        return {
            'total_opening_qty': float_round(row['total_opening_qty'] or 0.0, precision_digits=2),
            'total_incoming_qty': float_round(row['total_incoming_qty'] or 0.0, precision_digits=2),
            'total_outgoing_qty': float_round(row['total_outgoing_qty'] or 0.0, precision_digits=2),
            'total_virtual_available': float_round(row['total_virtual_available'] or 0.0, precision_digits=2),
            'total_stock_value': float_round(row['total_stock_value'] or 0.0, precision_digits=2),
            'total_incoming_value': float_round(row['total_incoming_value'] or 0.0, precision_digits=2),
            'total_outgoing_value': float_round(row['total_outgoing_value'] or 0.0, precision_digits=2),
            'total_virtual_value': float_round(row['total_virtual_value'] or 0.0, precision_digits=2),
        }

    def _empty_totals(self):
        """Retorna totales vacíos para cuando no hay datos."""
        return {
            'total_opening_qty': 0.0,
            'total_incoming_qty': 0.0,
            'total_outgoing_qty': 0.0,
            'total_virtual_available': 0.0,
            'total_stock_value': 0.0,
            'total_incoming_value': 0.0,
            'total_outgoing_value': 0.0,
            'total_virtual_value': 0.0,
        }

    def _get_inventory_movement_data(self, search_filters, pagerState={}):
        """Método principal que usa la consulta optimizada."""
        pagerState = pagerState or {}
        
        dates = self._get_date_range_dates(search_filters) or {}
        date_from = dates.get('date_from')
        date_to = dates.get('date_to')
        
        start_date = self._convert_to_utc(date_from, end_of_day=False) if date_from else None
        end_date = self._convert_to_utc(date_to, end_of_day=True) if date_to else None
        
        if not start_date or not end_date:
            return []
        
        locations = self._find_internal_locations(search_filters)
        if not locations:
            return []
        
        limit = pagerState.get('limit') or 0
        offset = pagerState.get('offset') or 0
        
        # Obtener company_id de los filtros para usar en la obtención de costos
        company_id = search_filters.get('company_id') or self.env.company.id
        
        return self._get_inventory_movement_data_optimized(
            search_filters, locations, start_date, end_date, limit, offset, company_id=company_id
        )

    # ==================== MÉTODOS AUXILIARES OPTIMIZADOS ====================
    
    def _get_names_batch(self, model, ids, field='name'):
        """Obtiene nombres en batch en lugar de uno por uno."""
        if not ids:
            return {}
        
        records = self.env[model].browse(ids)
        if field == 'complete_name':
            return {r.id: r.complete_name for r in records}
        return {r.id: r.name for r in records}

    def _build_product_domain(self, report_options):
        domain = [('is_storable', '=', True)]
        company_id = report_options.get('company_id')
        if company_id:
            domain += ['|',
                       ('company_id', '=', company_id),
                       ('company_id', '=', False)]
        if report_options.get('products'):
            domain += [('id', 'in', list(map(int, report_options['products'])))]
        if report_options.get('categories'):
            domain += [('categ_id', 'child_of', list(map(int, report_options['categories'])))]
        return domain

    # ==================== MÉTODOS DE REPORTES ====================
    
    @api.model
    def get_report_lines(self, options={}):
        options = options or {}
        results = self._get_inventory_movement_data(options, pagerState=options.get('pagerState'))
        if not results:
            raise ValidationError(_('There is no Inventory data available.'))

        lines = [{
            'name': '',
            'columns': [{'name': v} for v in [
                values['product_reference'] or '',
                values['product_name'],
                values.get('labhospy_supplier') or '',
                values['opening_qty'],
                values['incoming_qty'],
                values['outgoing_qty'],
                values['virtual_available'],
                values['stock_value'],
                values['incoming_value'],
                values['outgoing_value'],
                values['virtual_value'],
            ]],
        } for values in results]

        totals = self._get_header_values(results)
        lines.append(
            {
                'name': '',
                'level': 2,
                'columns': [{'name': ''}] * 11
            },
        )
        lines.append(
            {
                'name': '',
                'level': 2,
                'columns': [{'name': ''}, {'name': 'Total'}, {'name': ''}] + [
                    {"name": totals[f"total_{field}"]}
                    for _, field in self._report_display_fields()
                ],
            })
        return lines

    def get_report_pdf(self, options):
        IrConfig = self.env['ir.config_parameter'].sudo()
        layout = self.env.ref('web.minimal_layout', raise_if_not_found=False)
        if not layout:
            return {}
        base_url = IrConfig.get_param('report.url') or layout.get_base_url()
        rcontext = {
            'mode': 'print',
            'base_url': base_url,
            'company': self.env.company,
        }
        header = self.env['ir.actions.report']._render_template("web.internal_layout", values=rcontext)
        header = self.env['ir.actions.report']._render_template("web.minimal_layout", values=dict(rcontext, subst=True, body=Markup(header.decode())))

        context = dict(self.env.context)
        if context.get('active_id') and context.get('active_model'):
            rcontext['reference'] = self.env[context.get('active_model')].browse(int(context.get('active_id'))).display_name

        body = self.with_context(print_mode=True).get_html(options, options.get('pagerState'))['body']

        return self.env['ir.actions.report']._run_wkhtmltopdf(
            [body],
            header=header.decode(),
            landscape=True,
            specific_paperformat_args={'data-report-margin-top': 17, 'data-report-header-spacing': 12}
        )

    def print_pdf(self, options):
        context = dict(self.env.context)
        return {
            'type': 'ir_actions_stock_report_download',
            'data': {
                'model': context.get('model') or self._name,
                'options': json.dumps(options),
                'report_format': 'pdf',
            }
        }

    def get_xlsx(self, options, response):
        if not options:
            raise UserError(_("Report options are missing."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        default_col1_style = workbook.add_format({'font_name': 'Verdana', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Verdana', 'font_size': 12, 'font_color': '#666666'})
        title_style = workbook.add_format({'font_name': 'Verdana', 'bold': True, 'bottom': 2})
        super_col_style = workbook.add_format({'font_name': 'Verdana', 'bold': True, 'align': 'center'})
        level_0_style = workbook.add_format({'font_name': 'Verdana', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666'})
        level_1_style = workbook.add_format({'font_name': 'Verdana', 'bold': True, 'font_size': 13, 'bottom': 1, 'font_color': '#666666'})
        level_2_col1_style = workbook.add_format({'font_name': 'Verdana', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_2_col1_total_style = workbook.add_format({'font_name': 'Verdana', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_2_style = workbook.add_format({'font_name': 'Verdana', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_3_col1_style = workbook.add_format({'font_name': 'Verdana', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        level_3_col1_total_style = workbook.add_format({'font_name': 'Verdana', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_3_style = workbook.add_format({'font_name': 'Verdana', 'font_size': 12, 'font_color': '#666666'})

        sheet.set_column(0, 0, 20)
        sheet.set_column(0, 1, 30)

        super_columns = self._get_report_super_columns(options)
        y_offset = 6

        sheet.write(y_offset, 0, '', title_style)
        sheet.merge_range(0, 0, 0, 10, self._get_report_name()[:31], super_col_style)
        
        # Obtener nombres en batch
        if options.get('company_id'):
            company = self.env['res.company'].browse(options.get('company_id'))
            sheet.write(1, 0, "Company", super_col_style)
            sheet.write(2, 0, company.name)
        
        if options.get('categories'):
            categ_names = self._get_names_batch('product.category', options['categories'], 'complete_name')
            sheet.write(1, 1, "Categories", super_col_style)
            sheet.write(2, 1, ", ".join(categ_names.values()))
        
        if options.get('warehouses'):
            wh_names = self._get_names_batch('stock.warehouse', options['warehouses'])
            sheet.write(1, 2, "Warehouses", super_col_style)
            sheet.write(2, 2, ", ".join(wh_names.values()))
        
        if options.get('locations'):
            loc_names = self._get_names_batch('stock.location', options['locations'], 'complete_name')
            sheet.write(1, 3, "Locations", super_col_style)
            sheet.write(2, 3, ", ".join(loc_names.values()))

        if 'filter' in options.get('date', {}).keys():
            if options['date']['filter'] == 'today':
                sheet.write(3, 0, "Period As of", super_col_style)
                sheet.write(3, 1, options['date']['date_from'])
            if options['date']['filter'] in ('month', 'week', 'custom'):
                sheet.write(3, 0, "Period As of", super_col_style)
                sheet.write(3, 1, options['date']['date_from'])
                sheet.write(3, 2, "To", super_col_style)
                sheet.write(3, 3, options['date']['date_to'])

        x = super_columns.get('x_offset', 0)
        for super_col in super_columns.get('columns', []):
            cell_content = super_col.get('string', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
            x_merge = super_columns.get('merge')
            if x_merge and x_merge > 1:
                sheet.merge_range(0, x, 0, x + (x_merge - 1), cell_content, super_col_style)
                x += x_merge
            else:
                if cell_content == 'Internal Reference':
                    sheet.write(5, x, cell_content, super_col_style)
                else:
                    sheet.set_column(x, x, 25)
                    sheet.write(5, x, cell_content, super_col_style)
                x += 1
        
        lines = self.get_report_lines(options)
        
        for y in range(0, len(lines)):
            level = lines[y].get('level')
            if lines[y].get('caret_options'):
                style = level_3_style
                col1_style = level_3_col1_style
            elif level == 0:
                y_offset += 1
                style = level_0_style
                col1_style = style
            elif level == 1:
                style = level_1_style
                col1_style = style
            elif level == 2:
                style = level_2_style
                col1_style = 'total' in lines[y].get('class', '').split(' ') and level_2_col1_total_style or level_2_col1_style
            elif level == 3:
                style = level_3_style
                col1_style = 'total' in lines[y].get('class', '').split(' ') and level_3_col1_total_style or level_3_col1_style
            else:
                style = default_style
                col1_style = default_col1_style

            for x in range(0, len(lines[y]['columns'])):
                sheet.write(y + y_offset, x + lines[y].get('colspan', 1) - 1, lines[y]['columns'][x].get('name', ''), style)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

    def print_xlsx(self, options):
        context = dict(self.env.context)
        return {
            'type': 'ir_actions_stock_report_download',
            'data': {
                'model': context.get('model') or self._name,
                'options': json.dumps(options),
                'report_format': 'xlsx',
            }
        }

    # ==================== MÉTODO PRINCIPAL GET_HTML ====================
    
    def _parse_search_filters_JSON(self, search_filters):
        dates = self._get_date_range_dates(search_filters, display_for_qweb=True)
        search_filters.setdefault('date', {})
        search_filters['date'].update(dates)
        return search_filters

    def get_html(self, search_filters, pagerState={}):
        if isinstance(search_filters, str):
            search_filters = eval(search_filters)
        search_filters.setdefault('only_with_movements', True)
        context = dict(self.env.context)
        warehouses_obj = self.env['stock.warehouse'].sudo()
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        
        format_precision = lambda value: '{:,.{prec}f}'.format(value, prec=precision)

        records_count = self._count_products_with_movement(search_filters)
        limit_per_page = min(int(self.env['ir.config_parameter'].sudo().get_param(
                'stock_movement_report.inv_movement_rec_limit')) or 80, pagerState.get('limit', 80))

        if search_filters.get('pagerState') and context.get('print_mode'):
            pagerState = search_filters['pagerState']
        else:
            pagerState.update({'limit': limit_per_page})
        # Obtener company_id correctamente (puede ser ID o objeto)
        if search_filters.get('company_id', False):
            company_id = search_filters['company_id']
            # Asegurar que company_id sea un ID (entero)
            if not isinstance(company_id, int):
                company_id = int(company_id)
            # Obtener el objeto de la compañía
            company_id_obj = self.env['res.company'].sudo().browse(company_id)
        else:
            company_id_obj = self.env.company
            company_id = company_id_obj.id
        
        # Asegurar que search_filters tenga company_id como ID para pasarlo a los métodos
        if not search_filters.get('company_id'):
            search_filters['company_id'] = company_id
        
        if search_filters.get('warehouses'):
            warehouses = warehouses_obj.browse(search_filters.get('warehouses'))
            if (warehouses and not warehouses.mapped('company_id')) or warehouses.filtered(lambda wid: wid.company_id.id != company_id):
                search_filters['warehouses'] = []
            warehouses = warehouses_obj.browse(search_filters.get('warehouses'))
            locations = self.env['stock.location'].sudo().search([('id', 'in', search_filters.get('locations')),
                                                        '|', ('id', 'in', warehouses.mapped('view_location_id').ids),
                                                        ('location_id', 'child_of', warehouses.mapped('view_location_id').ids)])
            search_filters['locations'] = locations.ids
        
        lines = self._get_inventory_movement_data(search_filters, pagerState)
        if not lines and context.get('print_mode'):
            raise ValidationError(_('There is no any Inventory data available.'))
        base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Obtener nombres en batch (optimizado)
        options = self._parse_search_filters_JSON(search_filters)
        
        categories_name = ''
        warehouses_name = ''
        locations_name = ''
        
        if options.get('categories'):
            categ_names = self._get_names_batch('product.category', options['categories'], 'complete_name')
            categories_name = ", ".join(categ_names.values())
        
        if options.get('warehouses'):
            wh_names = self._get_names_batch('stock.warehouse', options['warehouses'])
            warehouses_name = ", ".join(wh_names.values())
        
        if options.get('locations'):
            loc_names = self._get_names_batch('stock.location', options['locations'], 'complete_name')
            locations_name = ", ".join(loc_names.values())

        # Calcular totales agregados de TODOS los productos (no solo la página actual)
        # Esto es esencial porque la paginación limita las líneas mostradas,
        # pero el header debe mostrar los totales de todo el inventario
        header_vals = self._get_aggregate_totals(search_filters)

        report_labels = self._get_report_qweb_labels()
        rcontext = {
            'mode': 'print',
            'base_url': base_url,
            'company': company_id_obj,
            'report_name': self._get_report_name(),
            'res_company': company_id_obj,
            'options': options,
            'categories': categories_name,
            'warehouses': warehouses_name,
            'locations': locations_name,
            'lines': lines,
            'header_vals': header_vals,
            'currency_id': company_id_obj.currency_id,
            'print_mode': context.get('print_mode', False),
            'format_precision': format_precision,
            'report_labels': report_labels,
        }

        values = {'report_name': self._get_report_name(),
            'res_company': company_id_obj,
            'options': options,
            'lines': lines,
            'header_vals': header_vals,
            'currency_id': company_id_obj.currency_id,
            'print_mode': context.get('print_mode', False),
            'format_precision': format_precision,
            'report_labels': report_labels,
        }
        body = self.env['ir.ui.view']._render_template(
            "stock_movement_report.print_template",
            values=dict(rcontext, values=values, report=self, context=self),
        )

        html = self.env['ir.qweb']._render('stock_movement_report.report_inventory_movement', values)

        replace_class = {'table-responsive': '', '<a': '<span', '</a>': '</span>'}
        if context.get('print_mode', False):
            for k, v in replace_class.items():
                html = html.replace(k, v)
        return {
            'html': html,
            'body': body,
            'buttons': self.get_reports_buttons(),
            'records_count': records_count,
            'limit_per_page': limit_per_page,
            'pagerState': pagerState,
            'search_filters': search_filters,
        }

    def search_read_products(self, product_ids, resIds):
        return self.env['product.product'].browse(product_ids).filtered(lambda product: product.categ_id.id in resIds).ids or []

    def search_read_locations(self, location_ids, resIds):
        return self.env['stock.location'].browse(location_ids).filtered(lambda location: location.warehouse_id.id in resIds).ids or []

    def search_read_categories(self, categories_ids, resIds):
        categories = self.env['product.product'].browse(resIds).mapped('categ_id')
        return self.env['product.category'].browse(categories_ids).filtered(lambda categ: categ.id in categories.ids).ids or []

    # Mantener métodos legacy para compatibilidad (pero no se usan)
    def _get_stock_move_data(self, domain, search_filters):
        """Método legacy - mantenido para compatibilidad."""
        return {}, {}
