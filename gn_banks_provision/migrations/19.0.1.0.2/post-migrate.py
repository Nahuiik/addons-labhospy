# -*- coding: utf-8 -*-
"""Actualiza secuencias PRO-/DC- en diarios de provisiones ya configurados."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env['res.company'].search([]):
        env['bank.provision.sequence.helper'].ensure_company_provision_sequences(company)
