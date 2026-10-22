# -*- coding: utf-8 -*-
# Antes de cargar datos: BD con group_hr_payroll_* apuntando a res.groups viejos (puente) rompe el XML.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_module_module
        SET state = 'uninstalled'
        WHERE name IN (
            'hr_payroll',
            'hr_work_entry_enterprise',
            'hr_payroll_account'
        )
        """
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    hn_user = env.ref("l10n_hn_payroll_base.group_hn_payroll_user", raise_if_not_found=False)
    hn_mgr = env.ref("l10n_hn_payroll_base.group_hn_payroll_manager", raise_if_not_found=False)
    if not hn_user or not hn_mgr:
        return
    IMD = env["ir.model.data"].sudo()
    for alias, target in (
        ("group_hr_payroll_user", hn_user),
        ("group_hr_payroll_manager", hn_mgr),
    ):
        row = IMD.search(
            [
                ("module", "=", "l10n_hn_payroll_base"),
                ("name", "=", alias),
            ],
            limit=1,
        )
        if row:
            old_gid = row.res_id if row.model == "res.groups" else None
            row.write({"model": "res.groups", "res_id": target.id})
            if old_gid and old_gid != target.id:
                old_g = env["res.groups"].browse(old_gid)
                if old_g.exists():
                    target.users |= old_g.users
        else:
            IMD.create(
                {
                    "name": alias,
                    "module": "l10n_hn_payroll_base",
                    "model": "res.groups",
                    "res_id": target.id,
                }
            )
