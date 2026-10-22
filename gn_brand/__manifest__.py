# -*- coding: utf-8 -*-
{
    'name': 'GN Brand',
    'version': '1.0.3',
    'summary': 'Campo personalizado para nombre en Systray',
    'description': """
Campo personalizado para nombre en Systray
==========================================

Este módulo permite personalizar el texto que aparece en el systray (barra superior) mediante un campo personalizado en la configuración de la empresa.

Características:
----------------
* Agrega un campo "Nombre Systray" en la configuración de la empresa
* El texto ingresado en este campo se muestra en el systray en lugar del nombre de la empresa
* Permite personalizar el texto visible en la barra superior
* Compatible con todas las versiones de Odoo 19.0+
    """,
    'category': 'Tools',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': ['web', 'base'],
    'data': [
        'views/res_company_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_brand/static/src/scss/systray_name.scss',
            'gn_brand/static/src/js/systray_name.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
