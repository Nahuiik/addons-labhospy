# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _bi_set_finance_menu_label(self):
        """Fuerza la etiqueta del app ``account.menu_finance`` a "Contabilidad"
        en los idiomas español activos (es*), evitando que se muestre
        "Facturación" (Invoicing) heredado del módulo ``account``.

        Se invoca desde ``account_app_branding.xml`` mediante ``<function>``
        para que se reaplique en cada instalación o actualización del módulo,
        no solo en el ``post_init_hook`` (que solo corre al instalar).
        """
        menu = self.env.ref("account.menu_finance", raise_if_not_found=False)
        if not menu:
            return
        codes = self.env["res.lang"].sudo().search(
            [("active", "=", True), ("code", "=like", "es%")]
        ).mapped("code")
        if not codes:
            return
        menu.update_field_translations(
            "name", {code: "Contabilidad" for code in codes}
        )
