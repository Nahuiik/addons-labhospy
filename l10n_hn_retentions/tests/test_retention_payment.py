# -*- coding: utf-8 -*-
"""Pruebas de la lógica de retenciones en pagos de proveedor.

Estas pruebas se centran en la lógica de cálculo y de los ``onchange`` del
asistente de pago (factura) y del formulario de pago: cómputo de la retención
12.5% solo para servicios, importe BRUTO del asistente (clave para que el
asiento no descuente la retención dos veces), preview de líneas de write-off y
reparto del importe respetando la retención por línea.

La verificación del asiento contable completo (banco neto, CxP por el total y
conciliación de la factura para 1%, 12.5%, 15% y la combinación 1%+12.5%, tanto
desde la factura como desde el formulario de pago) se realiza de forma
funcional contra la configuración real de la instancia; aquí no se postean
pagos porque la compañía sintética de pruebas no reproduce las secuencias de la
localización hondureña.
"""

from datetime import date

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestRetentionPayment(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # El usuario de pruebas de contabilidad no trae los grupos de los módulos
        # custom de GAMUNDI; el hook de creación de facturas (gn_lock_date)
        # consulta gn.period.lock y requiere ese acceso.
        lock_group = cls.env.ref('gn_lock_date.group_period_lock_manager',
                                 raise_if_not_found=False)
        if lock_group:
            cls.env.user.group_ids = [Command.link(lock_group.id)]

        # La localización HN (l10n_hn_account) exige año fiscal + periodo para la
        # fecha del asiento; la compañía sintética no los trae.
        cls._setup_fiscalyear()

        cls.ret_account_1 = cls.env['account.account'].create({
            'name': 'Retención 1% (test)', 'code': 'RET1TST',
            'account_type': 'liability_current',
            'company_ids': [Command.set(cls.env.company.ids)],
        })
        cls.ret_account_12 = cls.env['account.account'].create({
            'name': 'Retención 12.5% (test)', 'code': 'RET12TST',
            'account_type': 'liability_current',
            'company_ids': [Command.set(cls.env.company.ids)],
        })
        cls.ret_account_15 = cls.env['account.account'].create({
            'name': 'Retención 15% (test)', 'code': 'RET15TST',
            'account_type': 'liability_current',
            'company_ids': [Command.set(cls.env.company.ids)],
        })

        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('l10n_hn_retentions.apply_retentions', 'True')
        ICP.set_param('l10n_hn_retentions.apply_1', 'True')
        ICP.set_param('l10n_hn_retentions.apply_12_5', 'True')
        ICP.set_param('l10n_hn_retentions.apply_15', 'True')
        ICP.set_param('l10n_hn_retentions.account_ret_1', str(cls.ret_account_1.id))
        ICP.set_param('l10n_hn_retentions.account_ret_12_5', str(cls.ret_account_12.id))
        ICP.set_param('l10n_hn_retentions.account_ret_15', str(cls.ret_account_15.id))

        cls.service_product = cls.env['product.product'].create({
            'name': 'Servicio profesional (test)', 'type': 'service',
        })
        cls.goods_product = cls.env['product.product'].create({
            'name': 'Mercadería (test)', 'type': 'consu',
        })
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls._sin_counter = 0

    @classmethod
    def _setup_fiscalyear(cls):
        """Crea un año fiscal + periodos para la compañía de pruebas.

        El constraint de periodos de l10n_hn_account compara la compañía consigo
        misma (siempre verdadero), por lo que cualquier periodo solapado de otra
        compañía bloquea la creación. Para evitar choques con los periodos reales
        de la instancia usamos un año futuro libre (después del último periodo
        existente) tanto para el año fiscal como para la fecha de factura.
        """
        Fy = cls.env['account.fiscalyear'].sudo()
        Period = cls.env['account.period'].sudo()
        last = Period.search([], order='date_stop desc', limit=1)
        base_year = (last.date_stop.year + 2) if last else date.today().year
        cls.test_year = base_year
        cls.test_invoice_date = date(base_year, 6, 15)
        cls.fiscalyear = Fy.create({
            'name': 'FY-TEST-%s' % base_year,
            'code': 'FT%s' % str(base_year)[-4:],
            'company_id': cls.env.company.id,
            'date_start': date(base_year, 1, 1),
            'date_stop': date(base_year, 12, 31),
        })
        cls.fiscalyear.create_period()

    # ------------------------------------------------------------------ utils
    @classmethod
    def _next_sin(cls):
        cls._sin_counter += 1
        return '000-001-01-%08d' % cls._sin_counter

    @classmethod
    def _create_supplier_invoice(cls, product=None, price=2000.0):
        product = product or cls.service_product
        invoice = cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': cls.partner_a.id,
            'invoice_date': cls.test_invoice_date,
            'supplier_invoice_number': cls._next_sin(),
            'invoice_line_ids': [Command.create({
                'product_id': product.id,
                'quantity': 1,
                'price_unit': price,
                'tax_ids': [Command.set(cls.tax_purchase_a.ids)],
            })],
        })
        invoice.with_context(l10n_hn_customer_ref_post=True).action_post()
        return invoice

    def _new_register(self, invoice):
        pay_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type in ('liability_payable', 'asset_receivable'))
        return self.env['account.payment.register'].with_context(
            active_model='account.move.line', active_ids=pay_lines.ids,
        ).create({})

    # ============================================================ cómputo 12.5%
    def test_retention_type_assigned_to_service_line(self):
        inv = self._create_supplier_invoice(product=self.service_product)
        line = inv.invoice_line_ids
        self.assertTrue(
            line.retention_types_ids,
            "La línea de servicio debe recibir automáticamente el tipo de retención 12.5%.")

    def test_compute_12_5_for_service(self):
        inv = self._create_supplier_invoice(product=self.service_product, price=2000.0)
        wizard = self._new_register(inv)
        wizard.retention_12_5 = True
        wizard.compute_retention()
        self.assertAlmostEqual(wizard.amount_ret_12_5, 250.0, places=2,
                               msg="12.5% de 2000 (servicio) = 250.")

    def test_compute_12_5_zero_for_goods(self):
        inv = self._create_supplier_invoice(product=self.goods_product, price=2000.0)
        wizard = self._new_register(inv)
        wizard.retention_1 = True
        wizard.retention_12_5 = True
        wizard.compute_retention()
        self.assertAlmostEqual(wizard.amount_ret_12_5, 0.0, places=2,
                               msg="El 12.5% NO aplica a mercadería (solo servicios).")
        self.assertAlmostEqual(wizard.amount_ret_1, 20.0, places=2,
                               msg="El 1% sí aplica sobre la base (2000 * 1%).")

    # ====================================================== importe BRUTO (regresión)
    def test_onchange_retention_keeps_gross_amount(self):
        """El importe del asistente debe ser el BRUTO (residual), no el neto.

        Si se netara (residual - retención), el mecanismo de retención del pago
        descontaría la retención dos veces del banco y sobre-conciliaría la CxP.
        """
        inv = self._create_supplier_invoice(price=2000.0)
        wizard = self._new_register(inv)
        gross = wizard.source_amount
        wizard.retention_12_5 = True
        wizard.amount_ret_12_5 = 250.0
        wizard._onchange_retention()
        self.assertAlmostEqual(
            wizard.amount, gross, places=2,
            msg="El importe debe quedar en el bruto (%.2f), no neto." % gross)

    # =========================================================== preview write-off
    def test_single_retention_adds_one_writeoff_line(self):
        inv = self._create_supplier_invoice(price=2000.0)
        wizard = self._new_register(inv)
        wizard.retention_12_5 = True
        wizard.amount_ret_12_5 = 250.0
        wizard._onchange_retention()
        self.assertEqual(len(wizard.write_off_lines), 1)
        self.assertEqual(wizard.write_off_lines.account_id, self.ret_account_12)

    def test_two_retentions_without_1pct_add_two_lines(self):
        inv = self._create_supplier_invoice(price=2000.0)
        wizard = self._new_register(inv)
        wizard.retention_12_5 = True
        wizard.amount_ret_12_5 = 250.0
        wizard.retention_15 = True
        wizard.amount_ret_15 = 300.0
        wizard._onchange_retention()
        self.assertEqual(len(wizard.write_off_lines), 2)

    def test_no_retention_clears_writeoff_lines(self):
        inv = self._create_supplier_invoice(price=2000.0)
        wizard = self._new_register(inv)
        wizard.retention_12_5 = True
        wizard.amount_ret_12_5 = 250.0
        wizard._onchange_retention()
        self.assertEqual(len(wizard.write_off_lines), 1)
        wizard.retention_12_5 = False
        wizard.amount_ret_12_5 = 0.0
        wizard._onchange_retention()
        self.assertFalse(wizard.write_off_lines)
        self.assertEqual(wizard.payment_difference_handling, 'open')

    # ===================================================== reparto en formulario de pago
    def test_onchange_amount_caps_at_net_residual(self):
        """El reparto por factura debe topar en (residual - retención).

        El 'Importe' es el bruto; el banco saldrá neto. Cada línea no debe pasar
        de (residual - retención) para que (amount + retención) = residual y no
        salte "Amount to pay can not be greater than Amount Due".
        """
        inv = self._create_supplier_invoice(price=2000.0)
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier',
            'partner_id': self.partner_a.id, 'amount': 0.0,
            'journal_id': self.bank_journal.id,
        })
        line = self.env['payment.invoice.line'].create({
            'payment_id': payment.id, 'invoice_id': inv.id,
            'amount_total': inv.amount_total, 'residual': inv.amount_residual,
            'amount': 0.0,
        })
        payment.apply_retentions = True
        payment.apply_12_5 = True
        payment.changed_apply_1_or_apply_12_5()
        self.assertAlmostEqual(line.amount_retention_12_5, 250.0, places=2)
        # El usuario teclea el bruto (residual completo).
        payment.amount = inv.amount_residual
        payment.onchange_amount()
        self.assertAlmostEqual(
            line.amount, inv.amount_residual - 250.0, places=2,
            msg="La línea debe toparse en (residual - retención).")
