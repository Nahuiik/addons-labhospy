# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'gts_customer_advance')
class TestAdvanceCancelPermission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Test Cancel Anticipo',
        })
        cls.group_cancel_late = cls.env.ref(
            'gts_customer_advance.group_advance_cancel_after_day')
        cls.advance_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id),
            ('reconcile', '=', True),
        ], limit=1)
        cls.journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', 'in', ('bank', 'cash')),
        ], limit=1)
        if not cls.advance_account or not cls.journal:
            raise AssertionError(
                'Se requiere cuenta conciliable y diario banco/caja para las pruebas.'
            )
        cls.env['ir.config_parameter'].sudo().set_param(
            'gts_customer_advance.advance_account_id',
            str(cls.advance_account.id),
        )

    def _create_advance_payment(self):
        return self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 1000.0,
            'journal_id': self.journal.id,
            'is_advance': True,
            'advance_account_id': self.advance_account.id,
        })

    def _backdate_record(self, record, days=1):
        past = fields.Datetime.now() - timedelta(days=days)
        self.env.cr.execute(
            f'UPDATE {record._table} SET create_date = %s WHERE id = %s',
            (past, record.id),
        )
        record.invalidate_recordset(['create_date', 'advance_cancel_allowed'])

    def _remove_late_cancel_group(self):
        self.env.user.write({'group_ids': [(3, self.group_cancel_late.id)]})

    def _add_late_cancel_group(self):
        self.env.user.write({'group_ids': [(4, self.group_cancel_late.id)]})

    def test_advance_cancel_same_day_allowed(self):
        payment = self._create_advance_payment()
        self._remove_late_cancel_group()
        payment.action_cancel()
        self.assertEqual(payment.state, 'canceled')

    def test_advance_cancel_next_day_blocked_without_group(self):
        payment = self._create_advance_payment()
        self._backdate_record(payment)
        self._remove_late_cancel_group()
        with self.assertRaises(UserError):
            payment.action_cancel()

    def test_advance_cancel_next_day_allowed_with_group(self):
        payment = self._create_advance_payment()
        self._backdate_record(payment)
        self._add_late_cancel_group()
        payment.action_cancel()
        self.assertEqual(payment.state, 'canceled')

    def test_advance_link_reverse_next_day_blocked(self):
        payment = self._create_advance_payment()
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Test',
                'quantity': 1,
                'price_unit': 1000.0,
            })],
        })
        reclass = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'name': 'Test',
                    'account_id': self.advance_account.id,
                    'debit': 100.0,
                    'credit': 0.0,
                    'partner_id': self.partner.id,
                }),
                (0, 0, {
                    'name': 'Test',
                    'account_id': self.advance_account.id,
                    'debit': 0.0,
                    'credit': 100.0,
                    'partner_id': self.partner.id,
                }),
            ],
        })
        link = self.env['account.advance.link'].create({
            'payment_id': payment.id,
            'move_id': invoice.id,
            'reclass_move_id': reclass.id,
            'amount': 100.0,
        })
        self._backdate_record(link)
        self._remove_late_cancel_group()
        with self.assertRaises(UserError):
            link.action_reverse()

    def test_invoice_cancel_with_advance_next_day_blocked(self):
        payment = self._create_advance_payment()
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Test',
                'quantity': 1,
                'price_unit': 1000.0,
            })],
        })
        reclass = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'name': 'Test',
                    'account_id': self.advance_account.id,
                    'debit': 100.0,
                    'credit': 0.0,
                    'partner_id': self.partner.id,
                }),
                (0, 0, {
                    'name': 'Test',
                    'account_id': self.advance_account.id,
                    'debit': 0.0,
                    'credit': 100.0,
                    'partner_id': self.partner.id,
                }),
            ],
        })
        self.env['account.advance.link'].create({
            'payment_id': payment.id,
            'move_id': invoice.id,
            'reclass_move_id': reclass.id,
            'amount': 100.0,
        })
        self._backdate_record(invoice)
        self._remove_late_cancel_group()
        with self.assertRaises(UserError):
            invoice.button_cancel()
