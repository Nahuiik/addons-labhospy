# Copyright 2026 GN Solutions
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
{
    "name": "Informes contables por sucursal",
    "version": "19.0.1.0.2",
    "summary": "Filtro por sucursal (res.branch) en informes contables Enterprise",
    "author": "GN Solutions",
    "category": "Accounting/Accounting",
    "license": "LGPL-3",
    "depends": [
        "account_reports",
        "gts_branch_management",
    ],
    "data": [
        "views/account_report_views.xml",
        "data/account_report_branch_filter.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gn_financial_branch/static/src/components/account_report/filters/filters_inherit.xml",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
}
