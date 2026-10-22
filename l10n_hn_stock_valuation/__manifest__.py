# ©  2015-2020 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

{
    "name": "Stock Valuation Report",
    "summary": "Stock Valuation Report and Accounting Bridge",
    "version": "19.0.1.0.4",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "category": "Localization/Accounting",
    "depends": [
        # "deltatech_stock_date",  # de ce trebuie asta?
        "stock",
        "stock_account",
        "account",
        "purchase_stock",
        "sale_stock",
    ],
    "license": "OPL-1",
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/data.xml",
        "views/stock_inventory_views.xml",
        "wizard/stock_confirm_inventory_view.xml",
        "views/product_view.xml",
        "views/stock_quant_view.xml",
        "views/report_stockinventory.xml",
        # "views/stock_requests_count_view.xml",
        # "wizard/stock_change_product_qty_view.xml",
        "views/product_kanban_view.xml",
        "wizard/stock_inventory_merge.xml",
        "wizard/product_replenish_views.xml",
        "views/stock_valuation_report_views.xml",
        "wizard/stock_valuation_generate_entry_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_hn_stock_valuation/static/src/js/forecasted_patch.js",
            "l10n_hn_stock_valuation/static/src/xml/forecasted_buttons.xml",
        ],
    },
    "images": ["images/main_screenshot.png"],
    "installable": True,
    "development_status": "Production/Stable",
    "maintainers": ["dhongu"],
}
