# -*- coding: utf-8 -*-
{
    'name': 'Landed Cost Cancellation',
    'version': '19.0.1.0.4',
    'category': 'Inventory/Purchase',
    'summary': 'Cancel posted landed costs and reverse valuation',
    'description': (
        'Cancel landed costs and reverse journal entries and stock valuation. '
        'Includes list actions: cancel only, cancel and reset to draft, cancel and delete; '
        'configurable mode in Settings.'
    ),
    'author': 'Cybrosys Techno Solutions (migrado Realeza)',
    'website': 'https://www.cybrosys.com',
    'depends': ['stock_landed_costs'],
    'data': [
        'security/cancel_landed_cost_odoo_groups.xml',
        'security/ir.model.access.csv',
        'data/stock_landed_cost_data.xml',
        'views/stock_landed_cost_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
