# -*- coding: utf-8 -*-
###################################################################################
{
    'name': 'Enable UI Block Loader In Odoo',
    'version': '2.0.0',
    'sequence': 1,
    'summary': """Adds a UI blocking loader to Odoo 18, preventing actions while background processes are running.""",
    'description': 'Adds a UI blocking loader to Odoo 18, preventing actions while background processes are running.',
    'category': 'Extra Tools',
    'sequence': 1,
    'author': 'SVN IT Solutions',
    'company': 'SVN IT Solutions',
    'website': "",
    'depends': ['web'],
    'data': [],
    
    'assets': {
        'web.assets_backend': [
            "svn_enable_odoo_loader/static/src/js/svn_loading_indicator.js"
            ],
        },

    'demo': [],
    'images':['static/description/blockui v18 banner.png'],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'application': True,
}
