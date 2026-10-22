# -*- coding: utf-8 -*-
from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestHn904TaxSync(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.account_fiscal_country_id = cls.env.ref('base.hn')
        hn = cls.env.ref('base.hn')
        cls._tg_hn = cls.env['account.tax.group'].create({
            'name': 'TG HN test',
            'company_id': cls.env.company.id,
            'country_id': hn.id,
        })
        cls.tax_purchase_15 = cls.env['account.tax'].create({
            'name': 'ISV 15%',
            'amount_type': 'percent',
            'amount': 15,
            'type_tax_use': 'purchase',
            'country_id': hn.id,
            'company_id': cls.env.company.id,
            'tax_group_id': cls._tg_hn.id,
        })
        cls.tax_sale_exento = cls.env['account.tax'].create({
            'name': 'Exento',
            'amount_type': 'percent',
            'amount': 0,
            'type_tax_use': 'sale',
            'country_id': hn.id,
            'company_id': cls.env.company.id,
            'tax_group_id': cls._tg_hn.id,
        })

    def test_904_sync_sets_purchase_base_and_tax_tags(self):
        sync = self.env['l10n_hn_reports.904_tax_sync']
        self.assertGreater(sync.sync_company_taxes(self.env.company), 0)
        tag11 = self.env.ref('l10n_hn_reports.sar_tag_904_11')
        tag31 = self.env.ref('l10n_hn_reports.sar_tag_904_31')
        rep_base = self.tax_purchase_15.repartition_line_ids.filtered(
            lambda r: r.repartition_type == 'base'
        )
        rep_tax = self.tax_purchase_15.repartition_line_ids.filtered(
            lambda r: r.repartition_type == 'tax' and r.factor_percent
        )
        self.assertTrue(tag11 in rep_base.tag_ids)
        self.assertTrue(tag31 in rep_tax.tag_ids)

    def test_904_sync_sets_sale_exento_tag(self):
        sync = self.env['l10n_hn_reports.904_tax_sync']
        sync.sync_company_taxes(self.env.company)
        tag2 = self.env.ref('l10n_hn_reports.sar_tag_904_2')
        rep_base = self.tax_sale_exento.repartition_line_ids.filtered(
            lambda r: r.repartition_type == 'base'
        )
        self.assertTrue(tag2 in rep_base.tag_ids)

    def test_904_sync_skips_non_hn_company(self):
        country_us = self.env.ref('base.us')
        br = self.env['res.company'].create({
            'name': 'Branch US Test',
            'account_fiscal_country_id': country_us.id,
            'currency_id': self.env.ref('base.USD').id,
        })
        n = self.env['l10n_hn_reports.904_tax_sync'].sync_company_taxes(br)
        self.assertEqual(n, 0)
