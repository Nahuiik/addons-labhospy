# -*- coding: utf-8 -*-


# XML IDs declared by previous module versions but superseded by
# ``gn_banks_dashboard``. Cleaning them in Python (instead of an XML
# ``<delete>`` record) lets us silence warnings on databases that never
# had them while still cleaning up legacy installations.
_OBSOLETE_XML_IDS = (
    'gn_banks_ui.menu_banks_treasury_dashboard',
    'gn_banks_ui.action_gn_banks_treasury_dashboard',
)


def post_init_hook(cr_or_env, registry=None):
    """Sync workflow_state and UI labels for existing bank operations.

    Odoo 19 invoca post_init_hook(env). Versiones anteriores usaban (cr, registry).
    """
    if registry is not None:
        from odoo import SUPERUSER_ID, api

        env = api.Environment(cr_or_env, SUPERUSER_ID, {})
    else:
        env = cr_or_env
    _drop_obsolete_dashboard_menu(env)
    for model in ('debit.credit', 'bank.check', 'bank.transfer'):
        records = env[model].search([])
        if records:
            records._bank_ui_sync_workflow_state()
            records._compute_ui_operation_meta()


def _drop_obsolete_dashboard_menu(env):
    """Remove legacy treasury dashboard menu/action from upgraded databases."""
    for xml_id in _OBSOLETE_XML_IDS:
        record = env.ref(xml_id, raise_if_not_found=False)
        if record:
            record.sudo().unlink()
