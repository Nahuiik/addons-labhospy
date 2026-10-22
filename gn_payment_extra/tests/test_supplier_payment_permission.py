# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'gn_payment_extra')
class TestSupplierPaymentPermission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor Test Pago',
            'supplier_rank': 1,
        })
        cls.journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', 'in', ('bank', 'cash')),
        ], limit=1)
        cls.group_modify = cls.env.ref(
            'gn_payment_extra.group_supplier_payment_modify')

    def _create_supplier_payment(self, post=True):
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 500.0,
            'journal_id': self.journal.id,
        })
        if post:
            payment.action_post()
        return payment

    def _remove_modify_group(self):
        self.env.user.write({'group_ids': [(3, self.group_modify.id)]})

    def _add_modify_group(self):
        self.env.user.write({'group_ids': [(4, self.group_modify.id)]})

    def test_registered_payment_locked_without_group(self):
        payment = self._create_supplier_payment()
        self._remove_modify_group()
        self.assertTrue(payment.supplier_payment_locked)
        with self.assertRaises(UserError):
            payment.action_cancel()

    def test_registered_payment_cancel_with_group(self):
        payment = self._create_supplier_payment()
        self._add_modify_group()
        self.assertFalse(payment.supplier_payment_locked)
        payment.action_cancel()
        self.assertEqual(payment.state, 'canceled')

    def test_registered_payment_write_allowed_without_group(self):
        """write() no exige el permiso: el alta/posteo escribe nombre y campos técnicos.

        La edición manual en UI se bloquea con supplier_payment_locked (form edit=False).
        Cancelar / borrador / eliminar sí requieren el grupo.
        """
        payment = self._create_supplier_payment()
        self._remove_modify_group()
        self.assertTrue(payment.supplier_payment_locked)
        payment.write({'ref': 'memo post-create'})
        self.assertEqual(payment.ref, 'memo post-create')

    def test_draft_supplier_payment_editable_without_group(self):
        payment = self._create_supplier_payment(post=False)
        self._remove_modify_group()
        self.assertFalse(payment.supplier_payment_locked)
        payment.write({'ref': 'memo borrador'})
