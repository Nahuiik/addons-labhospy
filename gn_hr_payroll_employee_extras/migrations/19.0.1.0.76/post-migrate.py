# -*- coding: utf-8 -*-
# Migra residuo implícito (total manual − cuotas fijas) al campo loan_residual_amount.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Concept = env["hr.employee.recurring.concept"]
    updated = 0
    for rec in Concept.with_context(active_test=False).search(
        [("is_loan", "=", True), ("amount_type", "=", "fixed")]
    ):
        n = rec.installments or 0
        if n <= 0:
            continue
        if rec.first_quota_differentiated and (rec.first_quota_amount or 0.0) > 0:
            fixed = round(
                (rec.first_quota_amount or 0.0) + max(0, n - 1) * (rec.amount or 0.0),
                2,
            )
        else:
            fixed = round(n * (rec.amount or 0.0), 2)
        old_total = rec.total_amount or 0.0
        implicit = round(max(0.0, old_total - fixed), 2)
        if implicit > 0 and not (rec.loan_residual_amount or 0.0):
            rec.loan_residual_amount = implicit
            updated += 1
    if updated:
        _logger.info(
            "gn_hr_payroll_employee_extras 19.0.1.0.76: loan_residual_amount en %s préstamo(s)",
            updated,
        )
