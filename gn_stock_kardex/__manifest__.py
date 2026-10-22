# -*- coding: utf-8 -*-
{
    'name': 'Kardex AVCO (Tarjeta de Stock)',
    'version': '19.0.2.6.0',
    'category': 'Inventory/Reporting',
    'summary': 'Kardex / tarjeta de stock por producto con saldo y costo promedio (AVCO/FIFO)',
    'description': """
        Informe tipo Kardex basado en los datos nativos de valoración de Odoo
        (stock.avco.report: movimientos de stock y ajustes product.value).

        No sustituye a módulos de terceros; muestra movimientos en un rango de fechas
        con saldo acumulado y CMUP, exportable a PDF y Excel.

        Requiere categorías con método de costo Promedio o FIFO.
    """,
    'author': 'Grupo Nahuiik / Realeza',
    'license': 'LGPL-3',
    'depends': [
        'stock_account',
        'report_xlsx',
        'gts_branch_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/stock_kardex_wizard_views.xml',
        'wizards/stock_age_wizard_views.xml',
        'reports/report_reports.xml',
        'reports/stock_kardex_template.xml',
        'reports/stock_kardex_summary_template.xml',
        'reports/stock_age_template.xml',
        'views/product_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'gn_stock_kardex/static/src/kardex_preview/**/*.js',
            'gn_stock_kardex/static/src/kardex_preview/**/*.xml',
            'gn_stock_kardex/static/src/kardex_preview/**/*.scss',
            'gn_stock_kardex/static/src/stock_age_preview/**/*.js',
            'gn_stock_kardex/static/src/stock_age_preview/**/*.xml',
            'gn_stock_kardex/static/src/stock_age_preview/**/*.scss',
            'gn_stock_kardex/static/src/stock_dashboard/**/*.js',
            'gn_stock_kardex/static/src/stock_dashboard/**/*.xml',
            'gn_stock_kardex/static/src/stock_dashboard/**/*.scss',
        ],
    },
}
