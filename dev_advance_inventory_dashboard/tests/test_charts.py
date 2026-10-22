# -*- coding: utf-8 -*-

import logging
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.tests import tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestInventoryDashboardService(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref('dev_advance_inventory_dashboard.group_allow_access_inventory')
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'group_ids': [(4, cls.group.id)]})
        cls.service = cls.env['inventory.dashboard.service'].with_user(cls.admin)

    def test_get_filter_options(self):
        opts = self.service.get_filter_options()
        self.assertIn('warehouses', opts)
        self.assertIn('branches', opts)
        self.assertIn('period_presets', opts)
        self.assertTrue(opts['company_id'])

    def test_open_pickings_includes_open_incoming_or_outgoing(self):
        Picking = self.env['stock.picking']
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        self.assertTrue(warehouse, 'Se requiere al menos un almacén para la prueba')
        outgoing_type = warehouse.out_type_id
        product = self.env['product.product'].create({
            'name': 'Dashboard Open Picking Test',
            'type': 'consu',
        })
        parsed = self.service._parse_filters({'period': 'this_month'})
        scheduled = fields.Datetime.to_datetime(parsed['date_to'])

        picking = Picking.create({
            'picking_type_id': outgoing_type.id,
            'location_id': outgoing_type.default_location_src_id.id,
            'location_dest_id': outgoing_type.default_location_dest_id.id,
            'scheduled_date': scheduled,
            'move_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                'product_uom': product.uom_id.id,
                'location_id': outgoing_type.default_location_src_id.id,
                'location_dest_id': outgoing_type.default_location_dest_id.id,
            })],
        })
        picking.action_confirm()
        self.assertIn(picking.state, ('confirmed', 'assigned', 'waiting', 'partially_available'))

        domain = self.service._picking_domain(parsed, [
            ('picking_type_code', 'in', ('incoming', 'outgoing')),
            ('state', 'in', ('confirmed', 'assigned', 'waiting', 'partially_available')),
        ])
        direct_ids = Picking.search(domain).ids
        self.service._CACHE.clear()
        metrics = self.service._compute_metrics(parsed)
        self.assertEqual(metrics['open_pickings']['count'], len(direct_ids))
        self.assertIn(picking.id, metrics['open_pickings']['ids'])

    def test_get_dashboard_data(self):
        data = self.service.get_dashboard_data({'period': 'this_month'})
        self.assertIn('kpis', data)
        self.assertIn('charts', data)
        self.assertIn('health', data)
        self.assertGreater(len(data['kpis']), 0)
        self.assertIn('receipts_vs_deliveries', data['charts'])
        self.assertIn('abc_analysis', data['charts'])

    def test_get_dashboard_core(self):
        core = self.service.get_dashboard_core({'period': 'this_month'}, sparkline_days=30)
        self.assertIn('kpis', core)
        self.assertIn('health', core)
        self.assertIn('header', core)
        self.assertEqual(core['sparkline_days'], 30)
        kpi = core['kpis'][0]
        self.assertIn('sparkline', kpi)
        self.assertIn('sparkline_insufficient', kpi)
        self.assertIn('previous_value', kpi)
        self.assertIn('variation_pct', kpi)

    def test_get_dashboard_widgets(self):
        widgets = self.service.get_dashboard_widgets(
            {'period': 'this_month'}, ['charts', 'alerts'],
        )
        self.assertIn('charts', widgets)
        self.assertIn('alerts', widgets)

    def test_get_table_page_advanced(self):
        page = self.service.get_table_page_advanced(
            {'period': 'this_month'}, 'top_selling', 1, 10, '', '', {}, None,
        )
        self.assertIn('rows', page)
        self.assertIn('columns', page)
        self.assertGreater(len(page['columns']), 0)

    def test_sparkline_days_presets(self):
        opts = self.service.get_filter_options()
        self.assertIn('sparkline_days_presets', opts)
        ids = {p['id'] for p in opts['sparkline_days_presets']}
        self.assertEqual(ids, {7, 30, 90, 365})

    def test_get_table_page(self):
        page = self.service.get_table_page(
            {'period': 'this_month'}, 'top_selling', 1, 10, '', ''
        )
        self.assertIn('rows', page)
        self.assertIn('pages', page)

    def test_export_table_data(self):
        result = self.service.export_table_data(
            {'period': 'this_month'}, 'top_selling', 'csv', ''
        )
        self.assertIn('filename', result)
        self.assertIn('data', result)

    def test_get_drilldown_action(self):
        action = self.service.get_drilldown_action('out_of_stock', [], {'period': 'this_month'})
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertIn('domain', action)
        self.assertIn('views', action)
        self.assertTrue(action['views'])

    def test_get_executive_report_action(self):
        action = self.service.get_executive_report_action({'period': 'this_month'})
        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertIn('report_name', action)

    def test_get_resolve_action(self):
        action = self.service.get_resolve_action('out_of_stock', {'period': 'this_month'})
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertIn('views', action)
        self.assertTrue(action['views'])

    def test_get_user_layouts(self):
        layouts = self.service.get_user_layouts()
        self.assertIsInstance(layouts, list)
