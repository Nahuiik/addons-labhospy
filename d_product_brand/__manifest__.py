{
    'name': 'Product Brand',
    'version': '1.1',
    'category': 'Inventory',
    'summary': 'Add brand model for product, manage brand for each product',
    'description': """
        This module adds a brand model to replace the brand field in website sale schema.
    """,
    'depends': ['product', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_brand_views.xml',
        'views/product_template_views.xml',
    ],
    'author': "ndd",
    'website': "https://duong-odoo-apps.odoo.com",
    'support': "duongodooapps@gmail.com",
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'license': 'OPL-1',
}
