# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestBankUiWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.banks_require_approval = True
        cls.DebitCredit = cls.env['debit.credit']
        cls.Journal = cls.env['account.journal']
        cls.Account = cls.env['account.account']

        cls.journal = cls.Journal.search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        if not cls.journal:
            cls.journal = cls.Journal.create({
                'name': 'Banco UI Test',
                'type': 'bank',
                'code': 'BKUIT',
                'company_id': cls.company.id,
            })

        cls.expense = cls.Account.search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', 'in', ('expense', 'expense_direct_cost')),
        ], limit=1)
        if not cls.expense:
            cls.expense = cls.Account.create({
                'name': 'Gasto UI Test',
                'code': '900001',
                'account_type': 'expense',
                'company_ids': [(6, 0, [cls.company.id])],
            })

        cls.liability = cls.Account.search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', 'in', ('liability_current', 'liability_payable')),
        ], limit=1)
        if not cls.liability:
            cls.liability = cls.Account.create({
                'name': 'Pasivo UI Test',
                'code': '900002',
                'account_type': 'liability_current',
                'company_ids': [(6, 0, [cls.company.id])],
            })

    def _create_draft_debit(self):
        return self.DebitCredit.create({
            'move_type': 'debit',
            'description': 'UI workflow test',
            'journal_id': self.journal.id,
            'company_id': self.company.id,
            'date': fields.Date.today(),
            'total': 50.0,
            'debit_line_ids': [
                (0, 0, {'account_id': self.expense.id, 'amount': 50.0, 'type': 'debit'}),
            ],
        })

    def test_workflow_requires_approval(self):
        debit = self._create_draft_debit()
        self.assertEqual(debit.workflow_state, 'draft')
        with self.assertRaises(UserError):
            debit.action_validate()
        debit.action_submit_for_approval()
        self.assertEqual(debit.workflow_state, 'pending_approval')
        debit.action_approve()
        self.assertEqual(debit.workflow_state, 'approved')

    def test_ui_operation_meta_debit(self):
        debit = self._create_draft_debit()
        self.assertEqual(debit.ui_operation_type_key, 'debit')
        self.assertEqual(debit.ui_operation_type_label, 'Débito')

    def test_timeline_events_created(self):
        debit = self._create_draft_debit()
        events = debit.get_bank_timeline_events()
        self.assertTrue(any(e['kind'] == 'created' for e in events))

    def test_treasury_dashboard_rpc(self):
        data = self.env['banks.treasury.dashboard'].get_dashboard_data()
        self.assertIn('kpis', data)
        self.assertIn('charts', data)
        self.assertTrue(len(data['kpis']) >= 5)
