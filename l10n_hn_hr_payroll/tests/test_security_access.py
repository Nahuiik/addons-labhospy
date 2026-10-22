# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Tests de seguridad y accesos

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError

from .common import L10nHnPayrollTestCommon


@tagged('post_install', '-at_install', 'security')
class TestSecurityAccess(L10nHnPayrollTestCommon, TransactionCase):
    """Tests de permisos: admin puede, user/auditor restricciones"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = cls.env.ref('base.user_admin')
        # Asignar grupo Payroll Administrator para que admin pueda crear configs
        payroll_admin = cls.env.ref('l10n_hn_hr_payroll.group_hr_payroll_admin', raise_if_not_found=False)
        if payroll_admin:
            cls.admin_user.write({'group_ids': [(4, payroll_admin.id)]})

    def test_ihss_settings_admin_can_create(self):
        """Admin con grupo payroll puede crear IHSS settings"""
        settings = self.env['l10n.hn.ihss.settings'].with_user(self.admin_user).create({
            'year': 2027,
            'company_id': self.company.id,
            'ivm_ceiling_monthly': 20000.0,
            'ivm_employer_rate': 3.5,
            'ivm_employee_rate': 2.5,
            'em_ceiling_monthly': 20000.0,
            'em_employer_rate': 1.0,
            'em_employee_rate': 1.0,
            'payment_periodicity': 'biweekly',
        })
        self.assertTrue(settings.id)

    def test_isr_config_admin_can_create(self):
        """Admin puede crear ISR config"""
        config = self.env['l10n.hn.isr.config'].with_user(self.admin_user).create({
            'year': 2027,
            'company_id': self.company.id,
            'periodicity': 'biweekly',
            'apply_in': 'both',
            'salario_minimo_promedio': 13985.16,
        })
        self.assertTrue(config.id)

    def test_rap_settings_admin_can_create(self):
        """Admin puede crear RAP settings"""
        settings = self.env['l10n.hn.rap.settings'].with_user(self.admin_user).create({
            'year': 2027,
            'company_id': self.company.id,
            'foviif_floor_monthly': 15000.0,
            'foviif_employee_rate': 1.5,
            'foviif_employer_rate': 1.5,
            'frl_minimum_wage_high_scale': 10000.0,
            'frl_employer_rate': 4.0,
        })
        self.assertTrue(settings.id)

    def test_payroll_groups_exist(self):
        """Grupos de nómina Honduras existen"""
        admin_group = self.env.ref('l10n_hn_hr_payroll.group_hr_payroll_admin', raise_if_not_found=False)
        user_group = self.env.ref('l10n_hn_hr_payroll.group_hr_payroll_user', raise_if_not_found=False)
        auditor_group = self.env.ref('l10n_hn_hr_payroll.group_hr_payroll_auditor', raise_if_not_found=False)
        self.assertTrue(admin_group, "group_hr_payroll_admin debe existir")
        self.assertTrue(user_group, "group_hr_payroll_user debe existir")
        self.assertTrue(auditor_group, "group_hr_payroll_auditor debe existir")
