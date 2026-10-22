# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

{
    'name': 'Partner Ledger On Screen',
    'version': '19.0.1.2.6',
    'sequence': 1,
    'category': 'Sales',
    'description':
        """
         Odoo app will display Partner Ledger on customer screen

    Partner Ledger 
    Odoo partner Leadger 
    Odoo partner Details ledger
    Odoo due balance 
    Odoo Partner ledger Balance
        
    """,
    'summary': 'Odoo app will display Partner Ledger on customer screen partner Leadger Partner move line partner due balance partner overdue report',
    # Enterprise opcional (account_reports). Community: Reporte de seguimiento (partner.ageing) en bi_financial_reports_comm.
    'depends': ['contacts', 'account', 'bi_financial_reports_comm'],
    'data': [
        'views/account_move_line_partner_ledger_views.xml',
        'views/partner_view.xml',
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',

    # author and support Details =============#
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'https://www.devintellecs.com',
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd',
    'support': 'devintelle@gmail.com',
    'price': 19.0,
    'currency': 'EUR',
    'pre_init_hook': 'pre_init_check',
}
