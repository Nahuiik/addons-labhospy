
{
    'name': 'GTS Branch Management | Multiple Branch(Unit) Operation Setup for All Applications Odoo/OpenERP',
    'version': '19.0.1.0.25',
    'category': 'Sales',
    'author': 'Geo Technosoft',
    'website': 'https://www.geotechnosoft.com',
    'summary': 'Manage multiple Branch or multiple Unit Operations in company',
    'sequence': 1,
    'live_test_url': 'https://youtu.be/KN-fGNWOTTU',
    'description': (
        'Gestión de varias sucursales o unidades dentro de una misma compañía en ventas, compras, '
        'inventario y contabilidad, con roles por sucursal para el control de acceso.'
    ),
    'depends': ['base', 'sale', 'sale_management', 'purchase',
        'stock', 'account', 'professional_templates',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/account_common_report_wizard.xml',
        'views/res_branch_views.xml',
        'views/account_move.xml',
        'views/account_payment.xml',
        'views/purchase_order.xml',
        'views/res_users.xml',
        'views/sale_order.xml',
        'views/stock_location.xml',
        'views/stock_move.xml',
        'views/stock_picking.xml',
        'views/stock_warehouse.xml',
        'report/account_analysis_report.xml',

    ],
    'qweb': [],
    'images': ['static/description/banner.png'],
    'price': 49,
    'currency': 'USD',
    'license': 'OPL-1',
    'installable': True,
    'application': True
}
