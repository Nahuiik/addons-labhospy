# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    """Activa el filtro de sucursal en variantes de informe de impuestos si existen en la base."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    xmlids = (
        "account_reports.account.generic_tax_report",
        "account_reports.account.generic_tax_report_account_tax",
        "account_reports.account.generic_tax_report_tax_account",
    )
    for xid in xmlids:
        try:
            report = env.ref(xid, raise_if_not_found=False)
        except ValueError:
            continue
        if report and report.exists():
            report.write({"filter_res_branch": True})
