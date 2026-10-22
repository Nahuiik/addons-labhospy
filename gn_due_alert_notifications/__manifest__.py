# -*- coding: utf-8 -*-
{
    'name': 'Notificaciones de Vencimiento (CxP / CxC)',
    'version': '19.0.1.0.7',
    'category': 'Accounting',
    'summary': 'Tarjetas interactivas en tiempo real para alertas de vencimiento '
               'de facturas de proveedor y cliente.',
    'description': """
Notificaciones visuales de vencimiento
======================================

* Modelo persistente de control de alertas (sin duplicados).
* Tarjetas apiladas en tiempo real vía bus.bus + OWL.
* Centro de notificaciones con campana en systray.
* Configuración por compañía.
* Integración con gn_invoice_due_alerts y gn_customer_due_alerts.
    """,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'mail',
        'bus',
        'gn_invoice_due_alerts',
        'gn_customer_due_alerts',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/group_imply.xml',
        'data/cron_data.xml',
        'views/gn_due_alert_notification_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_due_alert_notifications/static/src/notifications/due_alert_stack.scss',
            'gn_due_alert_notifications/static/src/notifications/due_alert_card.xml',
            'gn_due_alert_notifications/static/src/notifications/due_alert_stack.xml',
            'gn_due_alert_notifications/static/src/notifications/due_alert_systray.xml',
            'gn_due_alert_notifications/static/src/notifications/due_alert_card.js',
            'gn_due_alert_notifications/static/src/notifications/due_alert_stack.js',
            'gn_due_alert_notifications/static/src/notifications/due_alert_bus_service.js',
            'gn_due_alert_notifications/static/src/notifications/due_alert_systray.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
