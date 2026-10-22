# -*- coding: utf-8 -*-
# Tras recargar traducciones del core, fuerza "Contabilidad" para el app account en español.

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
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
