# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from datetime import date, timedelta


@tagged('post_install', '-at_install', 'gn_due_alert_notifications')
class TestDueAlertNotifications(TransactionCase):

    _supplier_inv_seq = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'due_alert_enabled': True,
            'customer_due_alert_enabled': True,
            'gn_due_notif_enabled': True,
            'gn_due_notif_days_before': 3,
            'gn_due_notif_critical_days': 15,
            'gn_due_notif_realtime_enabled': True,
            'gn_due_notif_daily_summary_enabled': True,
            'gn_due_notif_daily_summary_hour': 8.0,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor Test Alertas'})
        cls.customer = cls.env['res.partner'].create({
            'name': 'Cliente Test CxC Apunte'})
        cls.user = cls.env.ref('base.user_admin')
        cls.group_payable = cls.env.ref(
            'gn_invoice_due_alerts.group_invoice_due_alert_user')
        cls.group_receivable = cls.env.ref(
            'gn_customer_due_alerts.group_customer_due_alert_user')
        cls.group_notif = cls.env.ref(
            'gn_due_alert_notifications.group_due_alert_notif_user')
        cls.user.write({'group_ids': [
            (4, cls.group_payable.id),
            (4, cls.group_receivable.id),
            (4, cls.group_notif.id),
        ]})
        cls.receivable_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        cls.journal_misc = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'general'),
        ], limit=1)

    def _next_supplier_number(self):
        type(self)._supplier_inv_seq += 1
        return '000-001-01-%08d' % type(self)._supplier_inv_seq

    def _sync_bill_due_date(self, move, due_date):
        """Terminos de pago locales pueden sobrescribir vencimiento al publicar."""
        move.write({'invoice_date_due': due_date})
        payable_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'liability_payable'
        )
        if payable_lines:
            payable_lines.write({'date_maturity': due_date})

    def _payable_line(self, move):
        engine = self.env['gn.due.alert.engine']
        return engine._invoice_alert_line(move, 'payable')

    def _create_bill(self, due_date, amount=1000.0, post=True):
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date.today(),
            'invoice_date_due': due_date,
            'company_id': self.company.id,
            'is_of_import': True,
            'supplier_invoice_number': self._next_supplier_number(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Linea test',
                'quantity': 1,
                'price_unit': amount,
            })],
        })
        if post:
            move.action_post()
            if due_date:
                self._sync_bill_due_date(move, due_date)
        return move

    def _create_receivable_entry(self, amount=5000.0, ref_date=None):
        ref_date = ref_date or date.today() - timedelta(days=10)
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_misc.id,
            'date': ref_date,
            'ref': 'Saldo inicial test CxC',
            'line_ids': [
                (0, 0, {
                    'name': 'CxC cliente test',
                    'partner_id': self.customer.id,
                    'account_id': self.receivable_account.id,
                    'debit': amount,
                    'credit': 0,
                    'date_maturity': ref_date,
                }),
                (0, 0, {
                    'name': 'Contrapartida',
                    'account_id': self.env['account.account'].search([
                        ('company_ids', 'in', self.company.id),
                        ('account_type', '=', 'equity'),
                    ], limit=1).id,
                    'debit': 0,
                    'credit': amount,
                }),
            ],
        })
        move.action_post()
        return move.line_ids.filtered(
            lambda l: l.partner_id == self.customer and l.debit > 0)

    def _engine(self):
        # SUDO-JUSTIFIED: pruebas simulan evaluacion del cron sin sesion interactiva.
        return self.env['gn.due.alert.engine'].sudo()

    def test_soon_alert_created(self):
        due = date.today() + timedelta(days=2)
        move = self._create_bill(due)
        self._engine()._evaluate_kind(
            self.company, 'payable')
        line = self._payable_line(move)
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ], limit=1)
        self.assertTrue(notif)
        self.assertEqual(notif.alert_level, 'soon')
        self.assertEqual(notif.source_type, 'invoice')

    def test_today_alert(self):
        move = self._create_bill(date.today())
        self._engine()._evaluate_kind(
            self.company, 'payable')
        line = self._payable_line(move)
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ], limit=1)
        self.assertEqual(notif.alert_level, 'today')

    def test_overdue_alert(self):
        move = self._create_bill(date.today() - timedelta(days=5))
        self._engine()._evaluate_kind(
            self.company, 'payable')
        line = self._payable_line(move)
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ], limit=1)
        self.assertEqual(notif.alert_level, 'overdue')

    def test_critical_alert(self):
        move = self._create_bill(date.today() - timedelta(days=20))
        self._engine()._evaluate_kind(
            self.company, 'payable')
        line = self._payable_line(move)
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ], limit=1)
        self.assertEqual(notif.alert_level, 'critical')

    def test_no_duplicate_notifications(self):
        move = self._create_bill(date.today())
        engine = self._engine()
        engine._evaluate_kind(self.company, 'payable')
        engine._evaluate_kind(self.company, 'payable')
        line = self._payable_line(move)
        count = self.env['gn.due.alert.notification'].search_count([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ])
        self.assertEqual(count, 1)

    def test_receivable_entry_alert(self):
        line = self._create_receivable_entry(
            ref_date=date.today() - timedelta(days=5))
        self._engine()._evaluate_kind(
            self.company, 'receivable')
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ])
        self.assertTrue(notif)
        self.assertEqual(notif.source_type, 'receivable_line')
        self.assertEqual(notif.alert_level, 'overdue')
        payload = notif._to_bus_payload()
        self.assertFalse(payload['can_register_payment'])
        self.assertIn('Saldo', payload['title'])

    def test_resolve_on_cancel(self):
        move = self._create_bill(date.today() - timedelta(days=3))
        engine = self._engine()
        engine._evaluate_kind(self.company, 'payable')
        line = self._payable_line(move)
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ], limit=1)
        self.assertTrue(notif)
        move.button_cancel()
        engine._evaluate_kind(self.company, 'payable')
        notif.invalidate_recordset()
        self.assertEqual(notif.state, 'resolved')

    def test_snooze(self):
        move = self._create_bill(date.today())
        self._engine()._evaluate_kind(
            self.company, 'payable')
        line = self._payable_line(move)
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ], limit=1)
        notif.with_user(self.user).action_snooze()
        self.assertEqual(notif.state, 'snoozed')
        self.assertTrue(notif.snoozed_until)

    def test_no_alert_without_due_date(self):
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date.today(),
            'company_id': self.company.id,
            'is_of_import': True,
            'supplier_invoice_number': self._next_supplier_number(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Sin vencimiento',
                'quantity': 1,
                'price_unit': 500,
            })],
        })
        move.action_post()
        move.write({'invoice_date_due': False})
        payable_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'liability_payable'
        )
        if payable_lines:
            payable_lines.write({'date_maturity': False})
        self._engine()._evaluate_kind(
            self.company, 'payable')
        line = self._payable_line(move)
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ])
        self.assertFalse(notif)

    def test_level_change_updates_record(self):
        move = self._create_bill(date.today() + timedelta(days=2))
        engine = self._engine()
        engine._evaluate_kind(self.company, 'payable')
        line = self._payable_line(move)
        notif = self.env['gn.due.alert.notification'].search([
            ('move_line_id', '=', line.id),
            ('user_id', '=', self.user.id),
        ], limit=1)
        self.assertEqual(notif.alert_level, 'soon')
        self._sync_bill_due_date(move, date.today() - timedelta(days=1))
        engine._evaluate_kind(self.company, 'payable')
        notif.invalidate_recordset()
        self.assertEqual(notif.alert_level, 'overdue')

    def test_bus_payload(self):
        self._create_bill(date.today())
        self._engine()._evaluate_kind(
            self.company, 'payable')
        payload = self.env['gn.due.alert.notification'].with_user(
            self.user).get_user_notifications_payload()
        self.assertTrue(payload.get('cards'))
        self.assertTrue(payload['pending_count'] >= 1)

    def test_daily_summary_hour_gate(self):
        Engine = self.env['gn.due.alert.engine']
        self.company.gn_due_notif_last_daily_summary_date = False
        self.assertTrue(Engine._should_send_daily_summary(self.company))
        Engine._mark_daily_summary_sent(self.company)
        self.assertFalse(Engine._should_send_daily_summary(self.company))
