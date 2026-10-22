# Copyright 2026 Grupo Nahuiik (parche LabHosPy)


def migrate(cr, version):
    from odoo.addons.account_financial_report.hooks import (
        _ensure_res_company_age_partner_column,
    )

    _ensure_res_company_age_partner_column(cr)
