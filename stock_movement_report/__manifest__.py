# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Inventory Movement Report (Onscreen, Excel and PDF)',
    'version': '19.0.1.3',
    'category': 'Warehouse',
    'summary': 'Inventory Movement Report (Onscreen, Excel and PDF)',
    'depends': ['stock_account', 'gn_labhospy'],
    'author': 'Synconics Technologies Pvt. Ltd.',
    'website': 'http://www.synconics.com',
    'live_test_url': 'https://youtu.be/reK-292wPTo',
    'description': """ Inventory movement report

    stock
    inventory
    movement
    report
    warehouse

""",
    'data': [
        'views/inventory_movement_report_views.xml',
        'views/res_config_settings_views.xml',
        'report/report_inventory_movement_templates.xml',
    ],
    'images': ['static/description/main_screen.png'],
    'assets': {
        'web.assets_backend': [
                '/stock_movement_report/static/src/scss/inventory_movement_report.scss',
                '/stock_movement_report/static/src/js/inventory_overview_table.js',
                '/stock_movement_report/static/src/xml/inventory_movement.xml',
                ],
        # 'web._assets_core': [
        #         '/stock_movement_report/static/src/core/pager/pager.xml'
        #     ]
        },
    'price': 149.0,
    'currency': 'EUR',
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'OPL-1',
}
