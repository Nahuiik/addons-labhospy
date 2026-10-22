# -*- coding: utf-8 -*-
{
    'name': 'Odoo Instance Agent - Monitoreo de Usuarios',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Agente de monitoreo de usuarios conectados para instancias Odoo',
    'description': """
Odoo Instance Agent - Monitoreo de Usuarios
============================================

Este módulo proporciona monitoreo de usuarios conectados para instancias Odoo.

Características principales:
* Tracking de usuarios activos/archivados
* Distinción entre usuarios Portal e Internos
* Monitoreo de actividad en última hora (configurable)
* Soporte multi-dispositivo por usuario
* Endpoints seguros para métricas y heartbeat
* Compatible con Odoo 8, 11, 14, 17, 19

Desarrollado para arquitectura multi-instancia con consola central.
    """,
    'author': 'Sistema de Monitoreo',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'portal',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/monitor_device_presence_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_instance_agent/static/src/js/heartbeat.js',
        ],
        'web.assets_frontend': [
            'odoo_instance_agent/static/src/js/heartbeat.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

