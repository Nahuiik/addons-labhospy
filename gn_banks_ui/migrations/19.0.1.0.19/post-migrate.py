# -*- coding: utf-8 -*-


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    for model in ('debit.credit', 'bank.check', 'bank.transfer'):
        if model not in env:
            continue
        records = env[model].search([])
        if records:
            records._compute_ui_operation_meta()
