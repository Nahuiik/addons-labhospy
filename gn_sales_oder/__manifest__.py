# -*- coding: utf-8 -*-
{
    'name': 'GN Sales Order',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Agrega número de factura a cotizaciones y picking',
    'description': """
        Agrega a las cotizaciones el numero de factura, agrega a el picking de la orden de venta el vendedor y el numero de factura
    """,
    'author': 'Realeza',
    'license': 'OPL-1',
    'depends': [
        'base',
        'sale',
        'stock',
        'account',
        'sale_stock',
    ],
    'data': [
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

