# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'gn_permissions')
class TestGnContactPermissions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_ro = cls.env.ref('gn_permissions.group_contact_manager_readonly')
        cls.group_ed = cls.env.ref('gn_permissions.group_contact_manager_editor')
        cls.group_sale = cls.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)

    def test_readonly_blocks_create_even_with_sale_acl(self):
        """Usuario con solo lectura + vendedor CRM no debe poder crear (ACL OR vs código)."""
        if not self.group_sale:
            self.skipTest('sales_team no instalado')
        login = 'gn_perm_test_ro_%s' % self.env.cr.dbname.replace('-', '_')[:20]
        user = self.env['res.users'].sudo().search([('login', '=', login)], limit=1)
        if user:
            user.sudo().unlink()
        user = (
            self.env['res.users']
            .sudo()
            .create(
                {
                    'name': 'Test GN RO',
                    'login': login,
                    'group_ids': [
                        (6, 0, (self.group_user | self.group_sale | self.group_ro).ids),
                    ],
                }
            )
        )
        Partner = self.env(user=user.id, su=False)['res.partner']
        self.assertTrue(Partner._gn_contact_readonly_profile())
        with self.assertRaises(AccessError):
            Partner.create({'name': 'X', 'company_type': 'person'})

    def test_editor_allows_create_with_sale_acl(self):
        if not self.group_sale:
            self.skipTest('sales_team no instalado')
        login = 'gn_perm_test_ed_%s' % self.env.cr.dbname.replace('-', '_')[:20]
        user = self.env['res.users'].sudo().search([('login', '=', login)], limit=1)
        if user:
            user.sudo().unlink()
        user = (
            self.env['res.users']
            .sudo()
            .create(
                {
                    'name': 'Test GN ED',
                    'login': login,
                    'group_ids': [
                        (6, 0, (self.group_user | self.group_sale | self.group_ed).ids),
                    ],
                }
            )
        )
        Partner = self.env(user=user.id, su=False)['res.partner']
        self.assertFalse(Partner._gn_contact_readonly_profile())
        p = Partner.create({'name': 'GN Test Partner OK', 'company_type': 'person'})
        self.assertTrue(p.id)
        p.sudo().unlink()

    def test_new_partner_gets_immediate_payment_terms(self):
        immediate = self.env.ref('account.account_payment_term_immediate')
        partner = self.env['res.partner'].create({
            'name': 'GN Test Immediate Terms',
            'company_type': 'person',
            'property_payment_term_id': self.env.ref('account.account_payment_term_30days').id,
        })
        self.assertEqual(partner.property_payment_term_id, immediate)
        self.assertEqual(partner.property_supplier_payment_term_id, immediate)
        partner.sudo().unlink()
