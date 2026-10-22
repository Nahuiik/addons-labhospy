# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'gn_product_traceability')
class TestProductTraceability(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env['product.traceability.service']
        cls.trace_group = cls.env.ref('gn_product_traceability_widget.group_traceability_user')
        cls.stock_user = cls.env.ref('stock.group_stock_user')
        cls.env.user.write({
            'group_ids': [(4, cls.trace_group.id), (4, cls.stock_user.id)],
        })

        cls.warehouse = cls.env['stock.warehouse'].search([], limit=1)
        cls.product = cls.env['product.product'].create({
            'name': 'Trace Test Product',
            'is_storable': True,
            'tracking': 'none',
        })
        cls.supplier_loc = cls.env.ref('stock.stock_location_suppliers')
        cls.stock_loc = cls.warehouse.lot_stock_id
        cls.customer_loc = cls.env.ref('stock.stock_location_customers')

    def test_classify_incoming(self):
        self.assertEqual(self.service.classify_movement('supplier', 'internal'), 'incoming')

    def test_classify_internal_transfer(self):
        self.assertEqual(self.service.classify_movement('internal', 'internal'), 'internal_transfer')

    def test_classify_outgoing(self):
        self.assertEqual(self.service.classify_movement('internal', 'customer'), 'outgoing')

    def test_net_stock_delta_internal_transfer(self):
        self.assertEqual(self.service._net_stock_delta('internal_transfer', 5.0), 0.0)

    def test_search_highlights(self):
        line = self.env['stock.move.line'].new({
            'origin': 'PO00123',
            'reference': 'PO00123',
        })
        result = self.service._search_highlights('po001', line, False, False, '')
        self.assertTrue(result['matched'])
        self.assertIn('origin', result['fields'])

    def test_flow_graph_structure(self):
        events = [{
            'id': 1,
            'document': 'WH/IN/0001',
            'source_id': 10,
            'source': 'Vendor',
            'source_usage': 'supplier',
            'destination_id': 20,
            'destination': 'Stock',
            'destination_usage': 'internal',
            'type_label': 'Recepción',
            'tone': 'success',
            'qty': 5,
            'uom': 'Units',
        }]
        graph = self.service._build_flow_graph(events)
        self.assertEqual(len(graph['nodes']), 3)
        self.assertTrue(len(graph['edges']) >= 2)

    def test_movement_type_summary(self):
        events = [
            {'type': 'incoming', 'type_label': 'Recepción', 'in_qty': 5, 'out_qty': 0},
            {'type': 'incoming', 'type_label': 'Recepción', 'in_qty': 3, 'out_qty': 0},
            {'type': 'outgoing', 'type_label': 'Entrega', 'in_qty': 0, 'out_qty': 2},
        ]
        summary = self.service._movement_type_summary(events)
        self.assertEqual(len(summary), 2)
        incoming = next(s for s in summary if s['type'] == 'incoming')
        self.assertEqual(incoming['count'], 2)
        self.assertEqual(incoming['qty_in'], 8)

    def test_movement_type_summary_includes_values(self):
        events = [
            {
                'type': 'incoming', 'type_label': 'Recepción',
                'in_qty': 5, 'out_qty': 0, 'value_in': 50.0, 'value_out': 0.0,
            },
            {
                'type': 'outgoing', 'type_label': 'Entrega',
                'in_qty': 0, 'out_qty': 2, 'value_in': 0.0, 'value_out': 20.0,
            },
        ]
        summary = self.service._movement_type_summary(events)
        incoming = next(s for s in summary if s['type'] == 'incoming')
        outgoing = next(s for s in summary if s['type'] == 'outgoing')
        self.assertEqual(incoming['value_in'], 50.0)
        self.assertEqual(outgoing['value_out'], 20.0)

    def test_no_product_returns_selector_payload(self):
        payload = self.service.get_product_traceability({})
        self.assertTrue(payload.get('needs_product'))
        self.assertIsNone(payload.get('product'))
        self.assertFalse(payload.get('events'))

    def test_get_traceability_empty_product(self):
        payload = self.service.get_product_traceability({'product_id': self.product.id})
        self.assertEqual(payload['product']['id'], self.product.id)
        self.assertEqual(payload['summary']['opening_qty'], 0.0)
        self.assertFalse(payload['events'])
        self.assertIn('flow_graph', payload)
        self.assertIn('movement_summary', payload)

    def test_kpis_include_extended_metrics(self):
        payload = self.service.get_product_traceability({'product_id': self.product.id})
        keys = {k['key'] for k in payload['kpis']}
        for expected in ('returns', 'adjustments', 'lots', 'reserved', 'incoming_pending', 'suppliers', 'customers'):
            self.assertIn(expected, keys)

    def test_stock_move_action_opens_client(self):
        move = self.env['stock.move'].create({
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'location_id': self.supplier_loc.id,
            'location_dest_id': self.stock_loc.id,
            'company_id': self.env.company.id,
        })
        action = move.action_open_traceability()
        self.assertEqual(action['tag'], 'gn_product_traceability_dashboard')
        self.assertEqual(action['params']['product_id'], self.product.id)

    def test_net_value_delta(self):
        self.assertEqual(self.service._net_value_delta('incoming', 100.0), 100.0)
        self.assertEqual(self.service._net_value_delta('outgoing', 100.0), -100.0)
        self.assertEqual(self.service._net_value_delta('internal_transfer', 100.0), 0.0)

    def test_costs_hidden_without_cost_group(self):
        payload = self.service.get_product_traceability({'product_id': self.product.id})
        self.assertFalse(payload['meta']['can_show_costs'])
        self.assertNotIn('opening_value', payload['summary'])
        keys = {k['key'] for k in payload['kpis']}
        for cost_kpi in ('inventory_value', 'avg_cost', 'net_value'):
            self.assertNotIn(cost_kpi, keys)

    def test_costs_visible_with_cost_group(self):
        cost_group = self.env.ref('gn_product_traceability_widget.group_traceability_cost')
        manager_group = self.env.ref('stock.group_stock_manager')
        self.env.user.write({'group_ids': [(4, cost_group.id), (4, manager_group.id)]})
        payload = self.service.get_product_traceability({'product_id': self.product.id})
        self.assertTrue(payload['meta']['can_show_costs'])
        self.assertIn('opening_value', payload['summary'])
        self.assertIn('total_value', payload['product'])
        keys = {k['key'] for k in payload['kpis']}
        self.assertIn('inventory_value', keys)
        self.assertIn('avg_cost', keys)
        self.assertIn('net_value', keys)

    def test_line_value_proration(self):
        cost_group = self.env.ref('gn_product_traceability_widget.group_traceability_cost')
        manager_group = self.env.ref('stock.group_stock_manager')
        self.env.user.write({'group_ids': [(4, cost_group.id), (4, manager_group.id)]})
        move = self.env['stock.move'].create({
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': 10.0,
            'location_id': self.supplier_loc.id,
            'location_dest_id': self.stock_loc.id,
            'company_id': self.env.company.id,
            'value_manual': 100.0,
        })
        move._action_confirm()
        move.move_line_ids.quantity = 10.0
        move.move_line_ids.picked = True
        move._action_done()
        move.invalidate_recordset(['value', 'is_valued'])
        self.assertTrue(move.is_valued)
        payload = self.service.get_product_traceability({'product_id': self.product.id})
        self.assertTrue(payload['events'])
        event = payload['events'][0]
        self.assertIn('value', event)
        self.assertAlmostEqual(event['value'], 100.0, places=2)
        self.assertAlmostEqual(event['value_balance'], 100.0, places=2)

    def test_commercial_partner_fields(self):
        vendor = self.env['res.partner'].create({'name': 'Proveedor ABC'})
        customer = self.env['res.partner'].create({'name': 'Cliente XYZ'})
        supplier_data = self.service._commercial_partner_fields('incoming', vendor)
        self.assertEqual(supplier_data['supplier'], 'Proveedor ABC')
        self.assertFalse(supplier_data['customer'])
        self.assertEqual(supplier_data['commercial_partner_label'], 'Comprado a')
        customer_data = self.service._commercial_partner_fields('outgoing', customer)
        self.assertEqual(customer_data['customer'], 'Cliente XYZ')
        self.assertFalse(customer_data['supplier'])
        self.assertEqual(customer_data['commercial_partner_label'], 'Vendido a')

    def test_access_denied_without_group(self):
        base_user = self.env.ref('base.group_user')
        user = self.env['res.users'].create({
            'name': 'No Trace User',
            'login': 'notrace_user_test2',
            'group_ids': [(6, 0, [base_user.id])],
        })
        with self.assertRaises(Exception):
            self.service.with_user(user).get_product_traceability({
                'product_id': self.product.id,
            })
