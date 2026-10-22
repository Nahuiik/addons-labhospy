# -*- coding: utf-8 -*-
{
    'name': "Cancelar Asientos Contables",

    'summary': """
        Agrega permisos para poder cancelar facturas y asientos contables.""",
    'license': 'OPL-1',
    'author': "Grupo Nahuiik - Mario Matamoros",
    'website': "http://www.gruponahuiik.com",

    'category': 'Accounting',
    'version': '19.0.1.0.1',

    'depends': ['base','account'],

    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/account_journal_inh.xml',
        'views/account_move_inh.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
