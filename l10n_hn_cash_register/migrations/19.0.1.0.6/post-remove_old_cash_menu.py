# -*- coding: utf-8 -*-

def migrate(cr, version):
    """Elimina el menú intermedio obsoleto (antes: Informes > Reportes de Caja Registradora)."""
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    data = env["ir.model.data"].sudo().search(
        [
            ("module", "=", "l10n_hn_cash_register"),
            ("name", "=", "cash_registers_accounting_menu"),
            ("model", "=", "ir.ui.menu"),
        ],
        limit=1,
    )
    if not data:
        return
    menu = env["ir.ui.menu"].sudo().browse(data.res_id)
    if menu.exists():
        menu.unlink()
