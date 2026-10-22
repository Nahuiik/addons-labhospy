{
    "name": "Honduras Stock",
    "summary": "Módulo de Inventario que agrega guía de remisión para Honduras",
    "description": (
        "Extensión de ventas, inventario y facturación para Honduras: guías de remisión, "
        "traslados entre tiendas, permisos de precios y costos, consumos internos y controles "
        "de stock. Ver README.md en el código para documentación detallada."
    ),
    "version": "19.0.3.5.62",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "license": "OPL-1",
    "category": "Tools",
    "depends": [
        "sale_management",
        "sale_stock",
        "stock",
        "account",
        "mail",
        "sale_margin",
        "sale_stock_margin",
        "stock_account",
        "stock_landed_costs",
        "gts_branch_management",
        "gn_labhospy",
        "gn_consume_product",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/stock_location_data.xml",
        "views/consume_reason_type_views.xml",
        "report/consume_exit_report_templates.xml",
        "report/consume_exit_report.xml",
        "views/sale_order_views.xml",
        "views/product_views.xml",
        "views/consume_product_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_company_views.xml",
        "views/product_category_views.xml",
        "views/stock_inventory_adjustment_name_views.xml",
        "views/account_move_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_location_views.xml",
        "views/res_branch_views.xml",
        "views/stock_inter_store_transfer_views.xml",
        "report/report_remission.xml",
        "report/report_remission_template.xml",
        "report/report_remission_inter_store_template.xml",
        "report/report_remission_inter_store.xml",
        "report/report_inter_store_transfer_template.xml",
        "report/report_inter_store_transfer.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "assets": {
        "web.assets_backend": [
            "l10n_hn_stock/static/src/scss/inter_store_transfer_list.scss",
        ],
    },
}



