# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Drop legacy treasury dashboard menu/action.

    They were declared by ``views/menu_dashboard_cleanup.xml`` (now removed)
    but the original ``views/menu_dashboard.xml`` was never wired into the
    manifest in this module, so the XML ``<delete>`` records emitted
    "External ID not found in the system" warnings on every upgrade.
    Doing the cleanup in Python with ``raise_if_not_found=False`` skips the
    warning when the records are already gone.
    """
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xml_id in (
        'gn_banks_ui.menu_banks_treasury_dashboard',
        'gn_banks_ui.action_gn_banks_treasury_dashboard',
    ):
        record = env.ref(xml_id, raise_if_not_found=False)
        if record:
            record.sudo().unlink()
