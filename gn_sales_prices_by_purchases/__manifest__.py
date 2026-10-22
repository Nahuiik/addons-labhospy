# -*- coding: utf-8 -*-
{
    'name': 'GN Precio venta desde compras',
    'version': '19.0.1.0.1',
    'summary': 'Actualiza P.V. y costo en plantilla al recibir compras con margen definido en la OC',
    'category': 'Tools',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': [
        'purchase_stock',
    ],
    'data': [
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
