# -*- coding: utf-8 -*-
"""Contratos de datos libro/DMC y puente con retenciones.

Los tests que publican vendor bills omiten temporalmente account.move.create
de ``gts_account_fiscal_year`` (exige account.period/FY que la suite account no crea).
"""

from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_hn_account.models.gts_account_fiscal_year import account_move as hn_gts_account_move
from odoo.addons.l10n_hn_account.models.gn_sar import account_invoice as hn_account_invoice_move
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_MOVEROS = hn_gts_account_move.AccountMove.__mro__
_GTS_ACCOUNT_MOVE_IX = _MOVEROS.index(hn_gts_account_move.AccountMove)
_GTS_ACCOUNT_MOVE_PARENT = _MOVEROS[_GTS_ACCOUNT_MOVE_IX + 1]


def _account_move_create_skip_gts_fiscal(self, vals_list):
    return _GTS_ACCOUNT_MOVE_PARENT.create(self, vals_list)


@tagged('post_install', '-at_install')
class TestDmcInvoiceRows(AccountTestInvoicingCommon):
    """Posted vendor bills vs filtro DMC (importación / gasto DMC)."""

    def setUp(self):
        super().setUp()
        p = patch.object(
            hn_gts_account_move.AccountMove,
            'create',
            _account_move_create_skip_gts_fiscal,
        )
        p.start()
        self.addCleanup(p.stop)

    def _invoice_period_bounds(self):
        inv_date = fields.Date.today().replace(day=15)
        return inv_date, inv_date.replace(day=1), fields.Date.end_of(inv_date, 'month')

    def test_dmc_excludes_vendor_bills_marked_import(self):
        inv_date, date_from, date_to = self._invoice_period_bounds()
        move = self.env['account.move'].sudo().create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': inv_date,
            'date': inv_date,
            'is_of_import': True,
            'supplier_invoice_number': 'IMP20510418-ONLY',
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_a.id,
                    'quantity': 1,
                    'price_unit': 111.11,
                }),
            ],
        })
        move.sudo().action_post()
        rows = self.env['l10n_hn_dmc.report_data'].build_invoice_rows(
            date_from, date_to, self.env.company)
        inv_total = round(move.amount_total, 2)
        self.assertFalse(
            any(
                round(r['monto_costo'] + r['monto_gasto'], 2) == inv_total
                for r in rows
            ),
            msg='Factura de importación no debe aparecer en el DMC.',
        )

    def test_dmc_excluir_compra_put_total_in_column_gasto(self):
        """excluir_compra (gasto DMC) → monto_gasto sin importación."""
        inv_date, date_from, date_to = self._invoice_period_bounds()
        sar_number = '001-003-07-76543218'
        with patch.object(
            hn_account_invoice_move.AccountMove,
            '_l10n_hn_sar_validation_before_post',
            lambda self: None,
        ):
            move = self.env['account.move'].sudo().create({
                'move_type': 'in_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': inv_date,
                'date': inv_date,
                'is_of_import': False,
                'excluir_compra': True,
                'supplier_invoice_number': sar_number,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': self.product_a.id,
                        'quantity': 1,
                        'price_unit': 250.5,
                    }),
                ],
            })
            move.sudo().action_post()
        rows = self.env['l10n_hn_dmc.report_data'].build_invoice_rows(
            date_from, date_to, self.env.company)
        inv_total = round(move.amount_total, 2)
        self.assertTrue(
            any(
                round(line['monto_gasto'], 2) == inv_total
                and abs(line['monto_costo']) < 1e-6
                for line in rows
            ),
            msg='Se esperaba monto_total en columnas de gasto (excluir_compra).',
        )


@tagged('post_install', '-at_install')
class TestHnLibroDmcPublic(TransactionCase):

    def test_libro_compras_payload_structure(self):
        data = self.env['hn.libro.report'].get_data_libro('compras', 2050, 1)
        self.assertIn('rows', data)
        self.assertIn('period', data)
        self.assertEqual(data['rows'], [])

    def test_dmc_get_data_empty_month(self):
        company = self.env.company
        df = fields.Date.from_string("2050-01-01")
        dt = fields.Date.end_of(df, "month")
        rows = self.env["l10n_hn_dmc.report_data"].build_invoice_rows(df, dt, company)
        self.assertEqual(rows, [])


@tagged('post_install', '-at_install')
class TestHnRetentionBridge(TransactionCase):

    def test_retention_field_when_l10n_hn_retentions_installed(self):
        if 'retention_types_ids' not in self.env['account.move.line']._fields:
            self.skipTest('l10n_hn_retentions no instalado')
        line = self.env['account.move.line'].new({'display_type': 'product'})
        self.assertTrue(hasattr(line, 'retention_types_ids'))
