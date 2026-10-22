# -*- coding: utf-8 -*-
"""Elimina reglas EXT2/DED2 definidas antes en gn_hn_hr_attendance (mismo xml id)."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_XML_NAMES = (
    "salary_rule_ext2_biweekly",
    "salary_rule_ded2_biweekly",
    "salary_rule_ext2_monthly",
    "salary_rule_ded2_monthly",
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Imd = env["ir.model.data"].sudo()
    Rule = env["hr.salary.rule"].sudo()
    data_rows = Imd.search(
        [("module", "=", "gn_hn_hr_attendance"), ("name", "in", _XML_NAMES)]
    )
    for row in data_rows:
        if row.res_id:
            rule = Rule.browse(row.res_id)
            if rule.exists():
                rule.unlink()
        row.unlink()
    # Regla de licencias por país pasó a gn_hr_payroll_licenses
    lic_imd = Imd.search(
        [
            ("module", "=", "l10n_hn_hr_payroll"),
            ("name", "=", "ir_rule_hr_license_type_country"),
        ]
    )
    for row in lic_imd:
        if row.model == "ir.rule" and row.res_id:
            env["ir.rule"].sudo().browse(row.res_id).unlink()
        row.unlink()
    _logger.info(
        "l10n_hn_hr_payroll 19.0.1.0.43 pre-migrate: EXT2/DED2 + regla licencias legacy"
    )
