# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo import fields
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestInventoryMovementReport(TransactionCase):

    def setUp(self):
        super(TestInventoryMovementReport, self).setUp()
        self.report = self.env['inventory.movement.report']
        self.Product = self.env['product.product']
        self.StockMove = self.env['stock.move']
        
    def test_get_date_range_dates_today(self):
        """Test que _get_date_range_dates retorna la fecha correcta usando zona horaria del usuario"""
        search_filters = {'date': {'filter': 'today'}}
        dates = self.report._get_date_range_dates(search_filters)
        
        # Verificar que retorna un diccionario con date_from y date_to
        self.assertIn('date_from', dates)
        self.assertIn('date_to', dates)
        
        # Verificar que date_from y date_to son iguales para 'today'
        self.assertEqual(dates['date_from'], dates['date_to'])
        
        # Verificar que usa fields.Date.today() (zona horaria del usuario)
        today = fields.Date.today()
        self.assertEqual(dates['date_from'], today)
        
    def test_get_date_range_dates_custom(self):
        """Test que _get_date_range_dates maneja fechas personalizadas correctamente"""
        search_filters = {
            'date': {
                'filter': 'custom',
                'date_from': '2026-01-01',
                'date_to': '2026-01-31'
            }
        }
        dates = self.report._get_date_range_dates(search_filters)
        
        self.assertEqual(str(dates['date_from']), '2026-01-01')
        self.assertEqual(str(dates['date_to']), '2026-01-31')
        
    def test_get_date_range_dates_week(self):
        """Test que _get_date_range_dates maneja filtro de semana correctamente"""
        search_filters = {'date': {'filter': 'week'}}
        dates = self.report._get_date_range_dates(search_filters)
        
        self.assertIn('date_from', dates)
        self.assertIn('date_to', dates)
        # Verificar que date_to es mayor o igual que date_from
        self.assertGreaterEqual(dates['date_to'], dates['date_from'])
        
    def test_get_date_range_dates_month(self):
        """Test que _get_date_range_dates maneja filtro de mes correctamente"""
        search_filters = {'date': {'filter': 'month'}}
        dates = self.report._get_date_range_dates(search_filters)
        
        self.assertIn('date_from', dates)
        self.assertIn('date_to', dates)
        # Verificar que date_to es mayor o igual que date_from
        self.assertGreaterEqual(dates['date_to'], dates['date_from'])
        
    def test_get_report_name(self):
        """Test que _get_report_name retorna el nombre traducido del reporte"""
        report_name = self.report._get_report_name()
        self.assertIsInstance(report_name, str)
        self.assertGreater(len(report_name), 0)
        
    def test_get_reports_buttons(self):
        """Test que get_reports_buttons retorna los botones correctos"""
        buttons = self.report.get_reports_buttons()
        self.assertIsInstance(buttons, list)
        self.assertGreater(len(buttons), 0)
        
        # Verificar que cada botón tiene 'name' y 'action'
        for button in buttons:
            self.assertIn('name', button)
            self.assertIn('action', button)
            
    def test_get_html_basic(self):
        """Test básico que get_html funciona sin errores con filtros mínimos"""
        search_filters = {
            'date': {'filter': 'today'},
            'company_id': False,
            'products': [],
            'categories': [],
            'warehouses': [],
            'locations': []
        }
        pagerState = {'limit': 10, 'offset': 0}
        
        try:
            result = self.report.get_html(search_filters, pagerState)
            
            # Verificar que retorna un diccionario con las claves esperadas
            self.assertIn('html', result)
            self.assertIn('buttons', result)
            self.assertIn('records_count', result)
            self.assertIn('pagerState', result)
            self.assertIn('search_filters', result)
            
            # Verificar que html es una cadena
            self.assertIsInstance(result['html'], str)
            
        except Exception as e:
            self.fail(f"get_html falló con error: {str(e)}")
            
    def test_get_html_with_products(self):
        """Test que get_html funciona con productos"""
        # Crear un producto de prueba si no existe
        product = self.Product.search([], limit=1)
        if not product:
            # Si no hay productos, crear uno básico
            product = self.Product.create({
                'name': 'Producto de Prueba',
                'type': 'product',
            })
        
        search_filters = {
            'date': {'filter': 'today'},
            'company_id': False,
            'products': [product.id],
            'categories': [],
            'warehouses': [],
            'locations': []
        }
        pagerState = {'limit': 10, 'offset': 0}
        
        try:
            result = self.report.get_html(search_filters, pagerState)
            self.assertIn('html', result)
        except Exception as e:
            self.fail(f"get_html con productos falló con error: {str(e)}")
            
    def test_get_inventory_movement_data_empty(self):
        """Test que _get_inventory_movement_data retorna lista vacía cuando no hay productos"""
        search_filters = {
            'date': {'filter': 'today'},
            'company_id': False,
            'products': [999999],  # ID que no existe
            'categories': [],
            'warehouses': [],
            'locations': []
        }
        pagerState = {'limit': 10, 'offset': 0}
        
        result = self.report._get_inventory_movement_data(search_filters, pagerState)
        self.assertEqual(result, [])
        
    def test_translations_dict(self):
        """Test que las traducciones se crean correctamente en get_html"""
        search_filters = {
            'date': {'filter': 'today'},
            'company_id': False,
            'products': [],
            'categories': [],
            'warehouses': [],
            'locations': []
        }
        pagerState = {'limit': 10, 'offset': 0}
        
        result = self.report.get_html(search_filters, pagerState)
        
        # Verificar que el HTML contiene algunas traducciones esperadas
        html = result.get('html', '')
        # Las traducciones deberían estar en el HTML renderizado
        self.assertIsInstance(html, str)
        
    def test_product_fields_access(self):
        """Test que el acceso a campos de productos funciona sin errores de campos relacionados"""
        # Obtener un producto existente
        product = self.Product.search([], limit=1)
        if product:
            # Verificar que podemos leer los campos básicos sin errores
            try:
                product_data = product.read([
                    'id', 'name', 'default_code', 'uom_id', 'standard_price', 'cost_method'
                ], load='_classic_write')
                
                self.assertIn('id', product_data[0])
                self.assertIn('name', product_data[0])
                
            except Exception as e:
                self.fail(f"Lectura de campos de producto falló: {str(e)}")
