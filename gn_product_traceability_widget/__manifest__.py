# -*- coding: utf-8 -*-
{
    'name': 'Product Traceability Widget',
    'version': '19.0.1.2.1',
    'category': 'Inventory/Inventory',
    'summary': 'Premium product traceability dashboard with timeline, flow map and exports',
    'author': 'Labhospy',
    'depends': ['stock', 'stock_account', 'product', 'web', 'report_xlsx'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_views.xml',
        'views/stock_lot_views.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_views.xml',
        'views/traceability_actions.xml',
        'wizard/traceability_export_wizard_views.xml',
        'report/traceability_report.xml',
        'report/traceability_report_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_product_traceability_widget/static/src/traceability/traceability_dashboard.scss',
            'gn_product_traceability_widget/static/src/traceability/**/*.js',
            'gn_product_traceability_widget/static/src/traceability/**/*.xml',
        ],
        'web.assets_web_dark': [
            'gn_product_traceability_widget/static/src/traceability/traceability_dashboard.dark.scss',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
