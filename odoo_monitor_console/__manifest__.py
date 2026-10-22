# -*- coding: utf-8 -*-
{
    'name': 'Odoo Monitor Console - Consola Central de Monitoreo',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Consola central para monitoreo de múltiples instancias Odoo',
    'description': """
Odoo Monitor Console - Consola Central
=======================================

Este módulo proporciona una consola central para monitorear múltiples instancias Odoo.

Características principales:
* Registro y gestión de instancias Odoo remotas
* Sincronización automática de métricas cada 1-5 minutos
* Dashboard consolidado con KPIs por instancia
* Lista consolidada de usuarios activos última hora
* Ranking de usuarios con más dispositivos
* Alertas y notificaciones (opcional)
* Compatible con instancias Odoo 8, 11, 14, 17, 19

Requiere que cada instancia tenga instalado el módulo odoo_instance_agent.
    """,
    'author': 'Sistema de Monitoreo',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/monitor_instance_views.xml',
        'views/monitor_user_snapshot_views.xml',
        'views/monitor_user_activity_line_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}

