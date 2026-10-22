# -*- coding: utf-8 -*-
"""Antes de cargar datos HN: XML IDs de licencias vuelven a l10n_hn_hr_payroll (ex gn_hr_driver_license).

Debe ser pre-migrate para que exista l10n_hn_hr_payroll.hr_license_type_action cuando
l10n_sv_hr_payroll resuelve el menú.
"""
import logging

_logger = logging.getLogger(__name__)

_NAMES = (
    "license_type_a",
    "license_type_b",
    "license_type_b1",
    "license_type_c",
    "license_type_c1",
    "license_type_ce",
    "license_type_d",
    "license_type_d1",
    "hr_license_type_view_list",
    "hr_license_type_view_form",
    "hr_license_type_action",
    "hr_employee_license_view_list",
    "hr_employee_license_view_form",
    "ir_rule_hr_license_type_country",
    "model_hr_license_type",
    "model_hr_employee_license",
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_model_data
        SET module = 'l10n_hn_hr_payroll'
        WHERE module = 'gn_hr_driver_license'
          AND name IN %s
        """,
        (_NAMES,),
    )
    n = cr.rowcount
    if n:
        _logger.info(
            "l10n_hn_hr_payroll 19.0.1.0.42 pre-migrate: %s XML IDs desde gn_hr_driver_license → HN",
            n,
        )
