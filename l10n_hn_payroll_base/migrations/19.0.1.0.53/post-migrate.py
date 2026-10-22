# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    employee_type = env.ref("hr.structure_type_employee", raise_if_not_found=False)
    if not employee_type:
        return
    Structure = env["hr.payroll.structure"]
    without = Structure.search([("type_id", "=", False)])
    if without:
        without.write({"type_id": employee_type.id})
        _logger.info(
            "l10n_hn_payroll_base: set default structure type on %s payroll structure(s)",
            len(without),
        )
