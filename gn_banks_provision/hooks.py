# -*- coding: utf-8 -*-


def post_init_hook(cr_or_env, registry=None):
    """Crea o actualiza secuencias PRO-/DC- en diarios de provisiones ya configurados.

    Odoo 19 invoca post_init_hook(env). Versiones anteriores usaban (cr, registry).
    """
    if registry is not None:
        from odoo.api import Environment
        env = Environment(cr_or_env, 1, {})
    else:
        env = cr_or_env
    for company in env['res.company'].search([]):
        env['bank.provision.sequence.helper'].ensure_company_provision_sequences(company)
