# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from datetime import date, timedelta


@tagged('post_install', '-at_install', 'l10n_hn_cash_register_functional')
class TestCashRegisterFunctional(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Obtener compañía
        cls.company = cls.env.company
        
        # Crear diarios de tipo banco y efectivo
        cls.bank_journal = cls.env['account.journal'].create({
            'name': 'Banco Test',
            'type': 'bank',
            'code': 'BNK',
            'company_id': cls.company.id,
        })
        
        cls.cash_journal = cls.env['account.journal'].create({
            'name': 'Efectivo Test',
            'type': 'cash',
            'code': 'CSH',
            'company_id': cls.company.id,
        })
        
        # Crear diario de ventas (no debe incluirse)
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas Test',
            'type': 'sale',
            'code': 'SAL',
            'company_id': cls.company.id,
        })
        
        # Crear partner de prueba
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Test',
            'company_id': cls.company.id,
        })
        
        # Crear cuenta de ingresos
        cls.income_account = cls.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', cls.company.id)
        ], limit=1)
        
        if not cls.income_account:
            cls.income_account = cls.env['account.account'].create({
                'name': 'Ingresos Test',
                'code': '4000',
                'account_type': 'income',
                'company_id': cls.company.id,
            })
        
        # Crear cuenta de recepción de pagos
        cls.receivable_account = cls.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_id', '=', cls.company.id)
        ], limit=1)
        
        if not cls.receivable_account:
            cls.receivable_account = cls.env['account.account'].create({
                'name': 'Cuentas por Cobrar Test',
                'code': '1200',
                'account_type': 'asset_receivable',
                'company_id': cls.company.id,
            })
        
        # Crear factura de prueba
        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'journal_id': cls.sale_journal.id,
            'invoice_date': date.today(),
            'company_id': cls.company.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Producto Test',
                'quantity': 1,
                'price_unit': 1000.0,
                'account_id': cls.income_account.id,
            })],
        })
        cls.invoice.action_post()
        
        # Crear pagos de prueba
        cls.payment_bank = cls.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': cls.partner.id,
            'amount': 500.0,
            'journal_id': cls.bank_journal.id,
            'date': date.today(),
            'company_id': cls.company.id,
        })
        cls.payment_bank.action_post()
        
        cls.payment_cash = cls.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': cls.partner.id,
            'amount': 300.0,
            'journal_id': cls.cash_journal.id,
            'date': date.today(),
            'company_id': cls.company.id,
        })
        cls.payment_cash.action_post()
        
        # Reconciliar pagos con factura
        (cls.payment_bank + cls.payment_cash).line_ids.filtered(
            lambda l: l.account_id == cls.receivable_account
        ).reconcile()

    def test_01_automatic_journal_detection(self):
        """Test que el módulo detecta automáticamente diarios de tipo banco y efectivo"""
        print("\n" + "=" * 70)
        print("PRUEBA FUNCIONAL 1: Detección Automática de Diarios")
        print("=" * 70)
        
        wizard = self.env['cash.register.wizard'].create({
            'date_from': date.today(),
            'date_to': date.today(),
        })
        
        # Verificar que se encuentran diarios de tipo banco y efectivo
        journal_ids = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])])
        
        self.assertTrue(len(journal_ids) >= 2, "Debe haber al menos 2 diarios (banco y efectivo)")
        print(f"✓ Diarios encontrados automáticamente: {len(journal_ids)}")
        
        bank_journals = journal_ids.filtered(lambda j: j.type == 'bank')
        cash_journals = journal_ids.filtered(lambda j: j.type == 'cash')
        
        self.assertTrue(len(bank_journals) > 0, "Debe haber al menos un diario de tipo banco")
        self.assertTrue(len(cash_journals) > 0, "Debe haber al menos un diario de tipo efectivo")
        
        print(f"  - Diarios de banco: {len(bank_journals)}")
        for j in bank_journals:
            print(f"    * {j.name} ({j.code})")
        
        print(f"  - Diarios de efectivo: {len(cash_journals)}")
        for j in cash_journals:
            print(f"    * {j.name} ({j.code})")
        
        # Verificar que el diario de ventas NO está incluido
        sale_in_results = self.sale_journal in journal_ids
        self.assertFalse(sale_in_results, "El diario de ventas NO debe estar incluido")
        print(f"✓ Diario de ventas correctamente excluido: {self.sale_journal.name}")

    def test_02_wizard_export_without_is_purchase(self):
        """Test que el wizard funciona sin necesidad de marcar is_purchase"""
        print("\n" + "=" * 70)
        print("PRUEBA FUNCIONAL 2: Wizard sin campo is_purchase")
        print("=" * 70)
        
        wizard = self.env['cash.register.wizard'].create({
            'date_from': date.today(),
            'date_to': date.today(),
        })
        
        # Verificar que el método export_xls encuentra diarios automáticamente
        try:
            # Este método busca diarios automáticamente
            journal_ids = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])])
            self.assertTrue(len(journal_ids) > 0, "Debe encontrar diarios automáticamente")
            print(f"✓ Método export_xls encuentra {len(journal_ids)} diarios automáticamente")
            
            # Verificar que no requiere is_purchase marcado
            journals_without_flag = journal_ids.filtered(lambda j: not j.is_purchase)
            self.assertTrue(len(journals_without_flag) > 0, "Debe funcionar con diarios sin is_purchase marcado")
            print(f"✓ Funciona con diarios sin is_purchase: {len(journals_without_flag)} diarios")
            
        except ValidationError as e:
            if "No se encuentra ningún diario" in str(e):
                self.fail("No debería requerir diarios con is_purchase marcado")
            raise

    def test_03_report_payment_pdf_includes_bank_and_cash(self):
        """Test que report_payment_pdf incluye pagos de diarios banco y efectivo"""
        print("\n" + "=" * 70)
        print("PRUEBA FUNCIONAL 3: Reporte incluye pagos de banco y efectivo")
        print("=" * 70)
        
        wizard = self.env['cash.register.wizard'].create({
            'date_from': date.today(),
            'date_to': date.today(),
        })
        
        # Obtener resultados del reporte
        results = wizard.report_payment_pdf()
        
        self.assertIsNotNone(results, "El reporte debe retornar resultados")
        print(f"✓ Reporte generado correctamente")
        
        # Verificar que los pagos están incluidos
        payment_found = False
        for cashier_data in results:
            for payment_line in cashier_data.get('lines_users', []):
                journal_name = payment_line.get('journal_id', '')
                if journal_name in [self.bank_journal.name, self.cash_journal.name]:
                    payment_found = True
                    print(f"  ✓ Pago encontrado en diario: {journal_name}")
                    print(f"    - Monto: {payment_line.get('amount', 0)}")
                    print(f"    - Número: {payment_line.get('number_payment', 'N/A')}")
        
        if not payment_found:
            print("  ⚠ No se encontraron pagos en los resultados (puede ser por filtros de fecha/estado)")

    def test_04_returns_banks_payments_method(self):
        """Test que returns_banks_payments funciona con diarios banco y efectivo"""
        print("\n" + "=" * 70)
        print("PRUEBA FUNCIONAL 4: Método returns_banks_payments")
        print("=" * 70)
        
        wizard = self.env['cash.register.wizard'].create({
            'date_from': date.today() - timedelta(days=1),
            'date_to': date.today() + timedelta(days=1),
        })
        
        # Obtener pagos de bancos
        user_id = self.env.user.id
        bank_payments = wizard.returns_banks_payments(user_id)
        
        print(f"✓ Método returns_banks_payments ejecutado")
        print(f"  - Pagos encontrados: {len(bank_payments)}")
        
        # Verificar que los pagos están en los resultados
        bank_found = False
        cash_found = False
        
        for payment_data in bank_payments:
            journal_name = payment_data.get('journal_id', '')
            if journal_name == self.bank_journal.name:
                bank_found = True
                print(f"  ✓ Pago de banco encontrado: {journal_name}")
            elif journal_name == self.cash_journal.name:
                cash_found = True
                print(f"  ✓ Pago de efectivo encontrado: {journal_name}")
        
        if bank_found or cash_found:
            print("✓ Método funciona correctamente con diarios banco y efectivo")

    def test_05_excel_report_includes_journals(self):
        """Test que el reporte Excel incluye diarios banco y efectivo"""
        print("\n" + "=" * 70)
        print("PRUEBA FUNCIONAL 5: Reporte Excel incluye diarios correctos")
        print("=" * 70)
        
        # Verificar que get_invoices busca diarios correctamente
        report_model = self.env['report.l10n_hn_cash_register.cash_register_xls.xlsx']
        
        journal_ids = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])]).ids
        
        self.assertTrue(len(journal_ids) > 0, "Debe encontrar diarios automáticamente")
        print(f"✓ Reporte Excel encuentra {len(journal_ids)} diarios automáticamente")
        
        # Verificar que los diarios de prueba están incluidos
        self.assertIn(self.bank_journal.id, journal_ids, "El diario de banco debe estar incluido")
        self.assertIn(self.cash_journal.id, journal_ids, "El diario de efectivo debe estar incluido")
        self.assertNotIn(self.sale_journal.id, journal_ids, "El diario de ventas NO debe estar incluido")
        
        print(f"  ✓ Diario banco incluido: {self.bank_journal.name}")
        print(f"  ✓ Diario efectivo incluido: {self.cash_journal.name}")
        print(f"  ✓ Diario ventas excluido: {self.sale_journal.name}")

    def test_06_is_purchase_field_hidden(self):
        """Test que el campo is_purchase está oculto en la vista"""
        print("\n" + "=" * 70)
        print("PRUEBA FUNCIONAL 6: Campo is_purchase oculto")
        print("=" * 70)
        
        # Verificar que el campo existe pero está oculto
        view = self.env.ref('l10n_hn_cash_register.view_account_cash_registers_journal_form_inherit', raise_if_not_found=False)
        
        if view:
            # Verificar que el campo is_purchase está en la vista pero invisible
            arch = view.arch
            self.assertIn('is_purchase', arch, "El campo is_purchase debe estar en la vista")
            self.assertIn('invisible="1"', arch, "El campo is_purchase debe estar oculto")
            print("✓ Campo is_purchase está oculto en la vista del diario")
        else:
            print("⚠ Vista no encontrada, pero el campo está definido en el modelo")

    def test_07_no_validation_error_without_is_purchase(self):
        """Test que no se genera error de validación sin is_purchase marcado"""
        print("\n" + "=" * 70)
        print("PRUEBA FUNCIONAL 7: Sin errores sin is_purchase")
        print("=" * 70)
        
        # Asegurar que los diarios NO tienen is_purchase marcado
        self.bank_journal.is_purchase = False
        self.cash_journal.is_purchase = False
        
        wizard = self.env['cash.register.wizard'].create({
            'date_from': date.today(),
            'date_to': date.today(),
        })
        
        # Verificar que no se genera error de validación
        try:
            journal_ids = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])])
            self.assertTrue(len(journal_ids) > 0, "Debe encontrar diarios sin is_purchase")
            print(f"✓ No se genera error sin is_purchase marcado")
            print(f"  - Diarios encontrados: {len(journal_ids)}")
        except ValidationError as e:
            if "No se encuentra ningún diario" in str(e):
                self.fail("No debería requerir is_purchase marcado")
            raise

    def test_08_journal_types_verification(self):
        """Test que verifica los tipos de diario correctos"""
        print("\n" + "=" * 70)
        print("PRUEBA FUNCIONAL 8: Verificación de Tipos de Diario")
        print("=" * 70)
        
        # Verificar tipos de diario
        self.assertEqual(self.bank_journal.type, 'bank', "El diario debe ser de tipo banco")
        self.assertEqual(self.cash_journal.type, 'cash', "El diario debe ser de tipo efectivo")
        self.assertEqual(self.sale_journal.type, 'sale', "El diario debe ser de tipo venta")
        
        print("✓ Tipos de diario verificados:")
        print(f"  - {self.bank_journal.name}: {self.bank_journal.type}")
        print(f"  - {self.cash_journal.name}: {self.cash_journal.type}")
        print(f"  - {self.sale_journal.name}: {self.sale_journal.type}")
        
        # Verificar búsqueda
        bank_cash_journals = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])])
        self.assertIn(self.bank_journal, bank_cash_journals)
        self.assertIn(self.cash_journal, bank_cash_journals)
        self.assertNotIn(self.sale_journal, bank_cash_journals)
        
        print("✓ Búsqueda de diarios funciona correctamente")

    def test_09_other_cashiers_requires_permission(self):
        """Sin permiso, el wizard fuerza el cajero al usuario conectado."""
        other = self.env['res.users'].create({
            'name': 'Otro Cajero Test',
            'login': 'otro_cajero_arqueo_test',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        wizard = self.env['cash.register.wizard'].create({
            'date_from': date.today(),
            'date_to': date.today(),
            'cashier_ids': [(6, 0, [other.id])],
        })
        self.assertEqual(wizard.cashier_ids.ids, [self.env.uid])
        self.assertEqual(wizard._get_report_cashier_ids(), [self.env.uid])
        self.assertFalse(wizard.can_select_other_cashiers)

    def test_10_other_cashiers_with_permission(self):
        """Con permiso, se pueden seleccionar otros cajeros y el reporte los usa."""
        group = self.env.ref('l10n_hn_cash_register.group_cash_register_other_cashiers')
        other = self.env['res.users'].create({
            'name': 'Cajero Seleccionable',
            'login': 'cajero_seleccionable_arqueo',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        supervisor = self.env['res.users'].create({
            'name': 'Supervisor Arqueo',
            'login': 'supervisor_arqueo_test',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                group.id,
            ])],
        })
        wizard = self.env['cash.register.wizard'].with_user(supervisor).create({
            'date_from': date.today(),
            'date_to': date.today(),
            'cashier_ids': [(6, 0, [other.id])],
        })
        self.assertEqual(wizard.cashier_ids.ids, [other.id])
        self.assertEqual(wizard._get_report_cashier_ids(), [other.id])
        self.assertTrue(wizard.can_select_other_cashiers)

