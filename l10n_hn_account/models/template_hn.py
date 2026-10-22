# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('hn')
    def _get_hn_template_data(self):
        return {
            'property_account_receivable_id': 'hn_101020101',
            'property_account_payable_id': 'hn_201010101',
            'property_account_expense_categ_id': 'hn_501010101',
            'property_account_income_categ_id': 'hn_401010101',
        }

    @template('hn', 'res.company')
    def _get_hn_res_company(self):
        return {
            self.env.company.id: {
                'anglo_saxon_accounting': False,
                'account_fiscal_country_id': 'base.hn',
                'cash_account_code_prefix': '1010101',
                'bank_account_code_prefix': '1010102',
                'transfer_account_code_prefix': '1010103',
                'account_default_pos_receivable_account_id': 'hn_101020205',
                'income_currency_exchange_account_id': 'hn_402010102',
                'expense_currency_exchange_account_id': 'hn_701010103',
                'account_journal_early_pay_discount_loss_account_id': 'hn_701010103',
                'account_journal_early_pay_discount_gain_account_id': 'hn_402010102',
                'account_sale_tax_id': 'l10n_hn_cta.tax_iva_15_venta',
                'account_purchase_tax_id': 'l10n_hn_cta.tax_iva_15_compra',
                'default_cash_difference_income_account_id': 'hn_402010102',
                'default_cash_difference_expense_account_id': 'hn_701010103',
            },
        }
