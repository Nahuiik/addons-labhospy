# -*- coding: utf-8 -*-

{
    'name': 'GN Permisos',
    'summary': 'Grupos de seguridad para gestión restringida de contactos',
    'version': '19.0.1.0.7',
    'category': 'Tools',
    'author': 'Labhospy',
    'license': 'LGPL-3',
    'depends': ['base', 'sale', 'account'],
    'data': [
        'security/gn_permissions_groups.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
