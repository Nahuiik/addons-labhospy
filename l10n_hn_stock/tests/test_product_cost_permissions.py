# -*- coding: utf-8 -*-

from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_hn_cost")
class TestProductCostPermissions(TransactionCase):
    """Permisos Ver costos vs Editar costo (standard_price)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref("base.group_user")
        cls.group_view = cls.env.ref("l10n_hn_stock.group_view_costs_margins")
        cls.group_edit = cls.env.ref("l10n_hn_stock.group_edit_product_cost")

    def test_view_only_user_has_readonly_flag(self):
        u = self.env["res.users"].create(
            {
                "name": "HN Test Solo ver costo",
                "login": "hn_test_view_cost_only",
                "group_ids": [Command.set([self.group_user.id, self.group_view.id])],
            }
        )
        p = self.env["product.product"].create({"name": "HN tmp cost ro", "type": "consu"})
        p_inv = p.with_user(u)
        p_inv.invalidate_recordset(["l10n_hn_standard_price_readonly"])
        self.assertTrue(
            p_inv.l10n_hn_standard_price_readonly,
            "Sin grupo Editar costo, el UI debe marcar costo como solo lectura",
        )

    def test_edit_group_user_can_edit_flag(self):
        u = self.env["res.users"].create(
            {
                "name": "HN Test Editar costo",
                "login": "hn_test_edit_cost",
                "group_ids": [Command.set([self.group_user.id, self.group_edit.id])],
            }
        )
        p = self.env["product.product"].create({"name": "HN tmp cost rw", "type": "consu"})
        p_inv = p.with_user(u)
        p_inv.invalidate_recordset(["l10n_hn_standard_price_readonly"])
        self.assertFalse(
            p_inv.l10n_hn_standard_price_readonly,
            "Con grupo Editar costo (implica Ver), el costo debe ser editable en UI",
        )

    def test_write_standard_price_product_00002_with_edit_group(self):
        product = self.env["product.product"].search(
            [("default_code", "=", "00002")], limit=1
        )
        if not product:
            self.skipTest("No hay producto con referencia interna 00002 en la base de prueba")

        u = self.env["res.users"].create(
            {
                "name": "HN Test 00002",
                "login": "hn_test_prod_00002",
                "group_ids": [Command.set([self.group_user.id, self.group_edit.id])],
            }
        )
        old = product.standard_price
        new_val = (old or 0.0) + 1.25
        product.with_user(u).write({"standard_price": new_val})
        product.invalidate_recordset()
        self.assertEqual(
            product.standard_price,
            new_val,
            "Usuario con Editar costo debe poder persistir standard_price en 00002",
        )
        product.with_user(u).write({"standard_price": old})
