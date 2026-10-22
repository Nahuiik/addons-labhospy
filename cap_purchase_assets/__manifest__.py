{
    'name': "Show assets on purchase",
    'category': "purchase",
    'author': "Captivea",
    'maintainer': 'Captivea',
    'contributors': ["Captivea"],
    'website': 'http://www.captivea.com/',
    'summary': "This app shows the lists of assets which are linked to purchase order",
    'version': '19.0.1.0',
    'description': """
    This modules shows the lists of all assets which are linked to purchase order line on purchase order 
    via smart button provided on purchase order after creating bills
    """,
    'depends': ['purchase', 'stock', 'account'],
    'data': ["views/purchase_order_form_view.xml"],
    'images': ['static/description/img/banner.gif', 'static/description/img/icon.png'],
    'price': 00,
    'currency': 'USD',
    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'auto_install': False,

}
