# -*- coding: utf-8 -*-
{
    'name': 'Labhospy — Acceso lectura para informes / QWeb',
    'summary': (
        'Permite a usuarios internos leer ir.asset e ir.ui.view para renderizar '
        'informes PDF/HTML sin requerir Administración ni Gestor Omux.'
    ),
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'author': 'Labhospy',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
}
