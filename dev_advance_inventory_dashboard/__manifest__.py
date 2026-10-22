# -*- coding: utf-8 -*-
{
    'name': 'Inventory Command Center',
    'version': '19.0.5.0.5',
    'sequence': 1,
    'category': 'Inventory/Inventory',
    'summary': 'Enterprise Inventory Command Center — analytics, KPIs, AI insights',
    'description': """
Inventory Command Center
========================

Centro de mando ejecutivo para inventarios: KPIs, gauge de salud, alertas,
insights IA, panel financiero, gráficos avanzados, layouts configurables y
reporte ejecutivo PDF.
    """,
    'license': 'AGPL-3',
    'depends': ['sale_management', 'purchase', 'stock', 'web', 'gts_branch_management'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'report/inventory_executive_report.xml',
        'views/dashboard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('include', 'web.chartjs_lib'),
            'dev_advance_inventory_dashboard/static/lib/echarts.min.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/chart_utils.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/echarts_utils.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/gauge_utils.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/export_utils.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/date_utils.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/components.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/components.xml',
            'dev_advance_inventory_dashboard/static/src/dashboard/viz_widget.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/viz_widget.xml',
            'dev_advance_inventory_dashboard/static/src/dashboard/advanced_data_table.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/advanced_data_table.xml',
            'dev_advance_inventory_dashboard/static/src/dashboard/inventory_dashboard.js',
            'dev_advance_inventory_dashboard/static/src/dashboard/inventory_dashboard.xml',
            'dev_advance_inventory_dashboard/static/src/dashboard/inventory_dashboard.scss',
            'dev_advance_inventory_dashboard/static/src/js/tour.js',
        ],
    },
    'installable': True,
    'application': True,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'pre_init_hook': 'pre_init_check',
}
