# -*- coding: utf-8 -*-
{
    'name': 'Clientes - Alertas de Cobro',
    'version': '19.0.1.0.12',
    'category': 'Accounting',
    'summary': 'Tablero tipo semaforo de facturas de cliente (CxC), '
               'con correos y notificaciones emergentes.',
    'description': """
Alertas de Vencimiento de Facturas de Cliente
=============================================

* Tablero tipo semaforo (vencidas / vencen hoy / proximas / futuras).
* Tablero de vencimientos por factura con KPIs y detalle por cliente.
* Tablero de antiguedad de CxC agrupado por cliente (0-30 / 31-60 / 61-90 / +90).
* Envio automatico de correo electronico N dias antes del vencimiento.
* Notificaciones emergentes para usuarios autorizados.
    """,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/cron_data.xml',
        'views/account_move_views.xml',
        'views/account_move_line_views.xml',
        'views/res_config_settings_views.xml',
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_customer_due_alerts/static/src/dashboard/dashboard_common.scss',
            'gn_customer_due_alerts/static/src/dashboard/dashboard.scss',
            'gn_customer_due_alerts/static/src/dashboard/traffic_dashboard.scss',
            'gn_customer_due_alerts/static/src/dashboard/aging_dashboard.scss',
            'gn_customer_due_alerts/static/src/dashboard/dashboard_utils.js',
            'gn_customer_due_alerts/static/src/dashboard/dashboard.xml',
            'gn_customer_due_alerts/static/src/dashboard/traffic_dashboard.xml',
            'gn_customer_due_alerts/static/src/dashboard/aging_dashboard.xml',
            'gn_customer_due_alerts/static/src/dashboard/dashboard.js',
            'gn_customer_due_alerts/static/src/dashboard/traffic_dashboard.js',
            'gn_customer_due_alerts/static/src/dashboard/aging_dashboard.js',
            'gn_customer_due_alerts/static/src/cxc_partner_list/cxc_partner_list_banner.scss',
            'gn_customer_due_alerts/static/src/cxc_partner_list/cxc_partner_list_banner.xml',
            'gn_customer_due_alerts/static/src/cxc_partner_list/cxc_partner_list_banner.js',
            'gn_customer_due_alerts/static/src/cxc_partner_list/cxc_partner_list_renderer.xml',
            'gn_customer_due_alerts/static/src/cxc_partner_list/cxc_partner_list_renderer.js',
            'gn_customer_due_alerts/static/src/cxc_partner_list/cxc_partner_list.js',
        ],
    },
    'installable': True,
    'application': True,
}
