# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestBankProvision(TransactionCase):
    """Tests for bank.provision accrual and FX differential flows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Provision = cls.env['bank.provision']
        cls.Account = cls.env['account.account']
        cls.Journal = cls.env['account.journal']
        cls.Sequence = cls.env['ir.sequence']

        cls.expense_account = cls.Account.search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', 'in', ('expense', 'expense_direct_cost')),
        ], limit=1)
        cls.liability_account = cls.Account.search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', 'in', ('liability_current', 'liability_payable')),
        ], limit=1)
        cls.assertTrue(cls.expense_account)
        cls.assertTrue(cls.liability_account)

        cls.accrual_journal = cls.Journal.create({
            'name': 'Provisiones Test',
            'code': 'PRVT',
            'type': 'general',
            'company_id': cls.company.id,
        })
        cls.company.banks_accrual_provision_journal_id = cls.accrual_journal
        cls.accrual_sequence = cls.Sequence.search([
            ('journal_id', '=', cls.accrual_journal.id),
            ('move_type', '=', 'provision'),
        ], limit=1)
        cls.assertTrue(cls.accrual_sequence)
        cls.assertEqual(cls.accrual_sequence.prefix, 'PRO-%(year)s-%(month)s-%(day)s-')
        cls.assertEqual(cls.accrual_sequence.padding, 5)

        cls.bank_journal = cls.Journal.search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        cls.assertTrue(cls.bank_journal)
        cls.assertTrue(cls.bank_journal.default_account_id)

        cls.fx_journal = cls.bank_journal
        cls.company.banks_fx_differential_journal_id = cls.fx_journal
        cls.fx_sequence = cls.Sequence.search([
            ('journal_id', '=', cls.fx_journal.id),
            ('move_type', '=', 'fx_differential'),
        ], limit=1)
        cls.assertTrue(cls.fx_sequence)
        cls.assertEqual(cls.fx_sequence.prefix, 'DC-%(year)s-%(month)s-%(day)s-')
        cls.assertEqual(cls.fx_sequence.padding, 5)

        if not cls.company.expense_currency_exchange_account_id:
            fx_account = cls.Account.search([
                ('company_ids', 'in', cls.company.id),
                ('account_type', 'in', ('expense', 'expense_direct_cost', 'income', 'income_other')),
            ], limit=1)
            cls.assertTrue(fx_account)
            cls.company.expense_currency_exchange_account_id = fx_account

        cls.branch = cls.env['res.branch'].search([], limit=1)

    def _create_accrual_provision(self, amount=100.0, branch=None):
        provision = self.Provision.create({
            'provision_kind': 'accrual',
            'description': 'Test accrual provision',
            'journal_id': self.accrual_journal.id,
            'company_id': self.company.id,
            'branch_id': branch.id if branch else False,
            'line_ids': [
                (0, 0, {
                    'account_id': self.expense_account.id,
                    'name': 'Expense line',
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': self.liability_account.id,
                    'name': 'Liability line',
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        })
        return provision

    def test_accrual_validate_creates_posted_move(self):
        provision = self._create_accrual_provision()
        provision.action_validate()
        self.assertEqual(provision.state, 'validated')
        self.assertTrue(provision.move_id)
        self.assertEqual(provision.move_id.state, 'posted')
        self.assertNotEqual(provision.name, '/')
        self.assertRegex(provision.name, r'^PRO-\d{4}-\d{2}-\d{2}-\d{5}$')

    def test_fx_sequence_format_preview(self):
        provision = self.Provision.create({
            'provision_kind': 'fx_differential',
            'description': 'FX preview',
            'journal_id': self.fx_journal.id,
            'company_id': self.company.id,
        })
        self.assertTrue(provision.dummy_name)
        self.assertRegex(provision.dummy_name, r'^DC-\d{4}-\d{2}-\d{2}-\d{5}$')

    def test_accrual_bank_journal_raises_validation(self):
        provision = self.Provision.create({
            'provision_kind': 'accrual',
            'description': 'Invalid journal',
            'journal_id': self.bank_journal.id,
            'company_id': self.company.id,
            'line_ids': [
                (0, 0, {
                    'account_id': self.expense_account.id,
                    'debit': 10.0,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': self.liability_account.id,
                    'debit': 0.0,
                    'credit': 10.0,
                }),
            ],
        })
        with self.assertRaises(ValidationError):
            provision._check_journal_matches_provision_kind()

    def test_fx_without_company_journal_raises_validation(self):
        self.company.banks_fx_differential_journal_id = False
        with self.assertRaises(ValidationError):
            self.Provision.create({
                'provision_kind': 'fx_differential',
                'description': 'FX missing journal config',
                'journal_id': self.bank_journal.id,
                'company_id': self.company.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': self.expense_account.id,
                        'debit': 5.0,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': self.liability_account.id,
                        'debit': 0.0,
                        'credit': 5.0,
                    }),
                ],
            })
        self.company.banks_fx_differential_journal_id = self.fx_journal

    def test_fx_template_lines(self):
        provision = self.Provision.create({
            'provision_kind': 'fx_differential',
            'description': 'FX template',
            'journal_id': self.fx_journal.id,
            'company_id': self.company.id,
        })
        provision.action_load_fx_template_lines()
        self.assertEqual(len(provision.line_ids), 2)
        self.assertEqual(provision.line_ids[0].account_id, self.fx_journal.default_account_id)
        contra = (
            self.company.expense_currency_exchange_account_id
            or self.company.income_currency_exchange_account_id
        )
        self.assertEqual(provision.line_ids[1].account_id, contra)

    def test_validate_without_sequence_raises(self):
        journal_no_seq = self.Journal.create({
            'name': 'No Seq Journal',
            'code': 'NSQJ',
            'type': 'general',
            'company_id': self.company.id,
        })
        provision = self.Provision.create({
            'provision_kind': 'accrual',
            'description': 'No sequence',
            'journal_id': journal_no_seq.id,
            'company_id': self.company.id,
            'line_ids': [
                (0, 0, {'account_id': self.expense_account.id, 'debit': 10.0, 'credit': 0.0}),
                (0, 0, {'account_id': self.liability_account.id, 'debit': 0.0, 'credit': 10.0}),
            ],
        })
        with self.assertRaises(UserError):
            provision.action_validate()

    def test_branch_propagated_to_move_lines(self):
        if not self.branch:
            self.skipTest('No res.branch available in test database.')
        provision = self._create_accrual_provision(branch=self.branch)
        provision.action_validate()
        self.assertEqual(provision.move_id.branch_id, self.branch)
        for line in provision.move_id.line_ids:
            self.assertEqual(line.branch_id, self.branch)
