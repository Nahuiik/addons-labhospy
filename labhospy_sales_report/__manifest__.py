# -*- coding: utf-8 -*-
{
    'name': 'LabHosPy — Reporte de ventas por período',
    'summary': 'Exporta ventas agrupadas por proveedor, producto, comercial y cliente con columnas por mes/trimestre/año.',
    'version': '19.0.1.0.1',
    'category': 'Sales',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'sale_stock',
        'stock',
        'gn_labhospy',
        'report_xlsx',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/labhospy_sales_report_wizard_views.xml',
        'report/labhospy_sales_report.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
