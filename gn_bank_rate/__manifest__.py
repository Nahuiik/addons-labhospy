# -*- coding: utf-8 -*-
{
    'name': 'GN Bank Currency Rate - BCH API',
    'version': '0.1.3',
    'author': 'Victor Amaya - Grupo Nahuiik',
    'website': 'http://gruponahuiik.com',
    'license': 'OPL-1',
    'description': """
        This module will get the currency rate from the Bank of Central Honduras API and update the currency rate in USD in the system. 
        Also, this module will send an email with the execution report of the cron job.
    """,
    'depends': ['base', 'mail', 'web'],
    'data': ['data/ir_cron.xml'],
    'assets': {
        'web.assets_backend': [
            'gn_bank_rate/static/src/js/bank_rate_systray.js',
            'gn_bank_rate/static/src/xml/bank_rate_systray.xml',
            'gn_bank_rate/static/src/scss/bank_rate_systray.scss',
        ],
    },
    'installable': True,
}
