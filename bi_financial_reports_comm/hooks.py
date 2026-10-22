# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api


def set_menu_finance_contabilidad(env):
    """Fuerza la etiqueta del app account para locales es*, evitando 'Facturación' (Invoicing)."""
    menu = env.ref("account.menu_finance", raise_if_not_found=False)
    if not menu:
        return
    codes = env["res.lang"].sudo().search(
        [("active", "=", True), ("code", "=like", "es%")]
    ).mapped("code")
    if not codes:
        return
    menu.update_field_translations(
        "name", {code: "Contabilidad" for code in codes}
    )


def post_init_hook(env):
    set_menu_finance_contabilidad(env)
