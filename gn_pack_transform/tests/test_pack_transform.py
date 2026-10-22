# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestGnPackTransform(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company._gn_pack_get_production_location()
        cls.warehouse = cls.env['stock.warehouse'].search([
            ('company_id', '=', cls.company.id),
        ], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')

        cls.product_unit = cls._create_product('Agua unidad test', standard_price=0.0)
        cls.product_pack = cls._create_product(
            'Agua pack 15 test',
            standard_price=100.0,
            unpack_product=cls.product_unit,
            unpack_ratio=15.0,
        )

        cls.env['stock.quant']._update_available_quantity(
            cls.product_pack, cls.stock_location, 5.0,
        )

    @classmethod
    def _create_product(cls, name, standard_price=0.0, unpack_product=False, unpack_ratio=0.0):
        tmpl = cls.env['product.template'].create({
            'name': name,
            'is_storable': True,
            'standard_price': standard_price,
            'uom_id': cls.uom_unit.id,
            'list_price': 1.0,
        })
        if unpack_product:
            tmpl.write({
                'gn_unpack_dest_product_id': unpack_product.id,
                'gn_unpack_ratio': unpack_ratio,
            })
        return tmpl.product_variant_id

    def _create_transform(self, source_qty=1.0):
        defaults = self.product_pack.product_tmpl_id._gn_pack_get_unpack_defaults(
            self.product_pack,
        )
        return self.env['gn.pack.transform'].create({
            'warehouse_id': self.warehouse.id,
            'source_product_id': self.product_pack.id,
            'source_uom_id': defaults['source_uom_id'],
            'source_qty': source_qty,
            'dest_product_id': defaults['dest_product_id'],
            'dest_uom_id': defaults['dest_uom_id'],
            'unpack_ratio': defaults['unpack_ratio'],
        })

    def test_transform_preserves_total_value(self):
        transform = self._create_transform(source_qty=2.0)
        expected_total = 200.0
        self.assertAlmostEqual(transform.source_total_value, expected_total, places=2)
        self.assertAlmostEqual(transform.dest_unit_cost, expected_total / 30.0, places=2)

        transform.action_confirm()

        self.assertEqual(transform.state, 'done')
        pack_qty = self.env['stock.quant']._get_available_quantity(
            self.product_pack, self.stock_location,
        )
        unit_qty = self.env['stock.quant']._get_available_quantity(
            self.product_unit, self.stock_location,
        )
        self.assertAlmostEqual(pack_qty, 3.0, places=2)
        self.assertAlmostEqual(unit_qty, 30.0, places=2)
