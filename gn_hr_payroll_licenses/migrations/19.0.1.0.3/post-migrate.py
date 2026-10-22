# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# Corrige ir.rule bloqueada por noupdate=True + dominio antiguo en modo global (sin grupos).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        """
        UPDATE ir_model_data
        SET noupdate = false
        WHERE module = 'gn_hr_payroll_licenses'
          AND name IN (
            'ir_rule_hr_license_type_country',
            'ir_rule_hr_license_type_admin_full'
          )
        """
    )
    country_rule = env.ref(
        "gn_hr_payroll_licenses.ir_rule_hr_license_type_country",
        raise_if_not_found=False,
    )
    if country_rule:
        country_rule.sudo().write(
            {
                "domain_force": "[('country_id', 'in', list(company_country_ids))]",
                "groups": [
                    (
                        6,
                        0,
                        [
                            env.ref("hr.group_hr_user").id,
                            env.ref("hr.group_hr_manager").id,
                            env.ref("l10n_hn_payroll_base.group_hn_payroll_user").id,
                            env.ref("l10n_hn_payroll_base.group_hn_payroll_manager").id,
                        ],
                    )
                ],
            }
        )
    admin_rule = env.ref(
        "gn_hr_payroll_licenses.ir_rule_hr_license_type_admin_full",
        raise_if_not_found=False,
    )
    if admin_rule:
        admin_rule.sudo().write(
            {
                "domain_force": "[(1, '=', 1)]",
                "groups": [(6, 0, [env.ref("base.group_system").id])],
            }
        )
