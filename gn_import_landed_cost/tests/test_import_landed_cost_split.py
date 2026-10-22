"""Pruebas del reparto por picking y del wizard de división de recepciones."""
from odoo.addons.stock_landed_costs.tests.common import TestStockLandedCostsCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestImportLandedCostSplit(TestStockLandedCostsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.landed_cost.landed_cost_ok = True
        cls.brokerage_quantity.landed_cost_ok = True
        cls.brokerage_quantity.split_method_landed_cost = 'by_quantity'

    def _make_incoming(self, product, qty):
        picking = self.Picking.create({
            'partner_id': self.supplier_id,
            'picking_type_id': self.warehouse.in_type_id.id,
            'location_id': self.supplier_location_id,
            'location_dest_id': self.warehouse.lot_stock_id.id,
        })
        move = self.Move.create({
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.supplier_location_id,
            'location_dest_id': self.warehouse.lot_stock_id.id,
        })
        picking.action_confirm()
        move.quantity = qty
        move.picked = True
        picking.button_validate()
        return picking

    def test_10_split_wizard_creates_second_picking(self):
        """El wizard divide una recepción en dos pickings con las cantidades pedidas."""
        # Preparar OC con dos líneas y su recepción borrador (usa flujo purchase).
        partner = self.env['res.partner'].browse(self.supplier_id)
        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'gn_labhospy_compra_internacional': True,
            'order_line': [
                (0, 0, {
                    'product_id': self.product_refrigerator.id,
                    'product_qty': 10,
                    'price_unit': 100,
                }),
                (0, 0, {
                    'product_id': self.product_oven.id,
                    'product_qty': 6,
                    'price_unit': 50,
                }),
            ],
        })
        po.button_confirm()
        self.assertTrue(po.picking_ids)
        picking1 = po.picking_ids[0]
        self.assertTrue(po.gn_import_split_available)

        wizard = self.env['purchase.split.reception.wizard'].with_context(
            default_purchase_id=po.id,
            default_picking_id=picking1.id,
        ).create({
            'purchase_id': po.id,
            'picking_id': picking1.id,
        })
        # default_get pobló las líneas.
        line_ref = wizard.line_ids.filtered(
            lambda l: l.product_id == self.product_refrigerator
        )
        line_oven = wizard.line_ids.filtered(
            lambda l: l.product_id == self.product_oven
        )
        line_ref.qty_first = 3
        line_ref.qty_second = 7
        line_oven.qty_first = 6
        line_oven.qty_second = 0
        wizard.action_confirm()

        pickings = po.picking_ids
        self.assertEqual(len(pickings), 2, 'Se esperan dos pickings tras dividir.')
        first = pickings.filtered(lambda p: p.gn_import_reception_part == 'first')
        second = pickings.filtered(lambda p: p.gn_import_reception_part == 'second')
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)

        ref_first = first.move_ids.filtered(
            lambda m: m.product_id == self.product_refrigerator
        )
        ref_second = second.move_ids.filtered(
            lambda m: m.product_id == self.product_refrigerator
        )
        self.assertEqual(ref_first.product_uom_qty, 3)
        self.assertEqual(ref_second.product_uom_qty, 7)
        # El horno solo está en la recepción 1.
        self.assertFalse(second.move_ids.filtered(
            lambda m: m.product_id == self.product_oven
        ))

    def test_20_cost_line_scope_picking_isolates_expense(self):
        """Una línea de LC con expense_scope=picking solo afecta a ese picking."""
        picking_a = self._make_incoming(self.product_refrigerator, 5)
        picking_b = self._make_incoming(self.product_oven, 10)

        cost = self.LandedCost.create({
            'picking_ids': [(6, 0, (picking_a | picking_b).ids)],
            'account_journal_id': self.stock_journal.id,
            'cost_lines': [
                (0, 0, {
                    'name': 'Flete importación',
                    'product_id': self.landed_cost.id,
                    'price_unit': 150,
                    'invoice_amount_lc': 150,
                    'split_method': 'by_quantity',
                    'expense_scope': 'global',
                }),
                (0, 0, {
                    'name': 'Derechos arancelarios',
                    'product_id': self.brokerage_quantity.id,
                    'price_unit': 100,
                    'invoice_amount_lc': 100,
                    'split_method': 'by_quantity',
                    'expense_scope': 'picking',
                    'picking_id': picking_b.id,
                }),
            ],
        })

        cost.compute_landed_cost()

        # Total de ajustes por línea de LC.
        global_line = cost.cost_lines.filtered(lambda l: l.expense_scope == 'global')
        picking_line = cost.cost_lines.filtered(lambda l: l.expense_scope == 'picking')
        adj_global = cost.valuation_adjustment_lines.filtered(
            lambda a: a.cost_line_id == global_line
        )
        adj_picking = cost.valuation_adjustment_lines.filtered(
            lambda a: a.cost_line_id == picking_line
        )

        self.assertEqual(len(adj_global), 2,
                         'Gasto global debe generar un ajuste por picking.')
        # Global 150 / 15 total = 10 por unidad; refri (5) = 50, horno (10) = 100.
        adj_global_refri = adj_global.filtered(
            lambda a: a.product_id == self.product_refrigerator
        )
        adj_global_oven = adj_global.filtered(
            lambda a: a.product_id == self.product_oven
        )
        self.assertAlmostEqual(adj_global_refri.additional_landed_cost, 50.0, places=2)
        self.assertAlmostEqual(adj_global_oven.additional_landed_cost, 100.0, places=2)

        # Picking-scoped: 100 / 10 hornos = 10 por unidad, total 100 solo en horno.
        self.assertEqual(len(adj_picking), 1,
                         'Gasto por picking solo debe alcanzar al picking indicado.')
        self.assertEqual(adj_picking.product_id, self.product_oven)
        self.assertAlmostEqual(adj_picking.additional_landed_cost, 100.0, places=2)

        # El refrigerador NO recibe el arancel.
        for adj in cost.valuation_adjustment_lines:
            if adj.product_id == self.product_refrigerator:
                self.assertEqual(
                    adj.cost_line_id.expense_scope,
                    'global',
                    'El refrigerador solo debe recibir el gasto global.',
                )
