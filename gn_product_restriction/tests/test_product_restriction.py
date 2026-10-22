# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'gn_product_restriction')
class TestGnProductRestriction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _user(self, login, group_xmlids):
        group_ids = [self.env.ref(x).id for x in group_xmlids]
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'group_ids': [(6, 0, group_ids)],
        })

    def test_create_template_denied_without_gn_group(self):
        user = self._user(
            'gn_test_no_gn',
            ['base.group_user', 'product.group_product_manager'],
        )
        with self.assertRaises(AccessError):
            self.env['product.template'].with_user(user).create({
                'name': 'Producto sin permiso GN',
            })

    def test_create_template_allowed_with_gn_group(self):
        user = self._user(
            'gn_test_with_gn',
            [
                'base.group_user',
                'product.group_product_manager',
                'gn_product_restriction.group_allow_product_create',
            ],
        )
        tmpl = self.env['product.template'].with_user(user).create({
            'name': 'Producto con permiso GN',
        })
        self.assertTrue(tmpl.id)

    def test_create_variant_denied_without_gn_group(self):
        user = self._user(
            'gn_test_var_no_gn',
            ['base.group_user', 'product.group_product_manager'],
        )
        tmpl = self.env['product.template'].create({'name': 'Base para variante'})
        with self.assertRaises(AccessError):
            self.env['product.product'].with_user(user).create({
                'name': 'Variante test',
                'product_tmpl_id': tmpl.id,
            })

    def test_write_still_allowed_with_manager_group(self):
        """Editar productos sigue controlado por el grupo estándar Productos/Crear."""
        user = self._user(
            'gn_test_write_ok',
            ['base.group_user', 'product.group_product_manager'],
        )
        tmpl = self.env['product.template'].create({'name': 'Para editar'})
        tmpl.with_user(user).write({'name': 'Editado OK'})
        self.assertEqual(tmpl.name, 'Editado OK')

    def test_write_denied_without_manager_group(self):
        """Sin Productos/Crear el usuario no puede editar (ACL estándar de Odoo)."""
        user = self._user(
            'gn_test_write_no',
            ['base.group_user'],
        )
        tmpl = self.env['product.template'].create({'name': 'Solo lectura'})
        with self.assertRaises(AccessError):
            tmpl.with_user(user).write({'name': 'Intento editar'})
