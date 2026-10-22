# -*- coding: utf-8 -*-
{
    'name': "Historial Compra/Venta",

    'summary': """
        Este módulo permite visualizar Ventas y compras en productos""",

    'description': """
        Este módulo permite visualizar en la ficha del producto el historial de compras y ventas realizadas desde las cotizaciones
    """,

    'author': "Grupo Nahuiik",
    'website': "http://www.gruponahuiik.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sales',
    'version': '19.0.1.0',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'purchase', 'account', 'sale'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'views/purchase_history.xml',
        'views/product_view.xml',
        'views/purchase_order_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
