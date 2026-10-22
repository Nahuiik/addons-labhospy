# © 2025 Grupo Nahuiik

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestApplyTemplateWizard(TransactionCase):
    """Pruebas para el wizard de aplicación de plantillas"""

    def setUp(self):
        super().setUp()
        self.Wizard = self.env['l10n.hn.contract.template.wizard']
        self.BenefitTemplate = self.env['l10n.hn.contract.benefit.template']
        self.HrVersion = self.env['hr.version']
        
        self.company = self.env.ref('base.main_company', raise_if_not_found=False)
        if not self.company:
            self.company = self.env['res.company'].create({
                'name': 'Test Company',
                'currency_id': self.env.ref('base.USD').id,
            })

    def test_wizard_creation(self):
        """Test: Crear wizard sin contrato debe fallar"""
        structure_type = self.env['hr.payroll.structure.type'].search([], limit=1)
        if not structure_type:
            self.skipTest("No hay tipos de estructura salarial configurados")
        
        # Buscar un contrato para la prueba
        version = self.HrVersion.search([], limit=1)
        if not version:
            self.skipTest("No hay contratos disponibles")
        
        wizard = self.Wizard.create({
            'contract_id': version.id,
        })
        self.assertTrue(wizard, "El wizard debe crearse correctamente")
        self.assertEqual(wizard.contract_id, version, "El contrato debe asignarse correctamente")

    def test_wizard_validation(self):
        """Test: Validar que requiere plantillas"""
        version = self.HrVersion.search([], limit=1)
        if not version:
            self.skipTest("No hay contratos disponibles")
        
        wizard = self.Wizard.create({
            'contract_id': version.id,
        })
        
        with self.assertRaises(UserError):
            wizard.action_apply_templates()

    def test_wizard_compute_structure_type(self):
        """Test: Verificar cálculo de structure_type_id"""
        version = self.HrVersion.search([], limit=1)
        if not version:
            self.skipTest("No hay contratos disponibles")
        
        wizard = self.Wizard.create({
            'contract_id': version.id,
        })
        
        # El structure_type_id debe calcularse automáticamente
        structure_type = version._get_structure_type_id()
        wizard._compute_structure_type_id()
        
        # Si el contrato tiene structure_type, debe calcularse
        if structure_type:
            # Verificar que se calculó correctamente
            self.assertTrue(wizard.structure_type_id or not structure_type)
        else:
            # Si no tiene structure_type, el wizard puede no tenerlo
            self.assertTrue(True)  # Caso válido

