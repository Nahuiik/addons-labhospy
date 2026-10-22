{
    'name': 'Today Yesterday Filter in Invoices',
    'version': '17.0',
    'category': 'Account',
    'summery': 'This app will Filter Today and yesterdays invoices, purchase orders, sale orders and journal items',
    'author': 'INKERP',
    'website': "http://www.inkerp.com",
    'depends': ['account', 'purchase', 'sale'],
    
    'data': [
        'views/account_invoice_view.xml',
        'views/purchase_order_view.xml',
        'views/sale_order_view.xml',
        'views/account_move_line_view.xml',
    ],
    
    'images': ['static/description/banner.png'],
    'license': "OPL-1",
    'installable': True,
    'application': True,
    'auto_install': False,
}
