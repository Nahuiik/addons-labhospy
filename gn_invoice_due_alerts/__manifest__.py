# -*- coding: utf-8 -*-
{
    'name': 'Alertas de Vencimiento de Facturas',
    'version': '19.0.1.0.7',
    'category': 'Accounting',
    'summary': 'Tablero tipo semáforo de facturas de proveedor y préstamos bancarios, '
               'con correos y notificaciones emergentes a usuarios autorizados.',
    'description': """
Alertas de Vencimiento de Facturas de Proveedor
===============================================

* Tablero tipo semáforo (vencidas / vencen hoy / próximas / futuras).
* Tablero de vencimientos por factura con KPIs y detalle por proveedor.
* Tablero de antigüedad de CxP agrupado por proveedor (0-30 / 31-60 / 61-90 / +90).
* Tablero de vencimientos de préstamos bancarios con semáforo de cuotas mensuales.
* Maestro de préstamos importado desde el detalle de cuotas (BAC, Ficohsa, etc.).
* Vínculo con débitos bancarios (gn_banks) para registrar el pago de cada cuota.
* Envío automático de correo electrónico N días antes del vencimiento y el
  día del vencimiento.
* Notificaciones emergentes (toast) en cualquier pantalla de Odoo para los
  usuarios con el permiso.
* Grupo de seguridad dedicado: solo lo ven los usuarios autorizados.
    """,
    'author': 'Equipo de tecnología (microlab/GN)',
    'website': 'https://github.com/jackjack82',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'mail',
        'gn_banks',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/bank_loan_data.xml',
        'data/mail_template_data.xml',
        'data/cron_data.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/dashboard_views.xml',
        'views/bank_loan_views.xml',
        'views/debit_credit_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_invoice_due_alerts/static/src/dashboard/dashboard_common.scss',
            'gn_invoice_due_alerts/static/src/dashboard/dashboard.scss',
            'gn_invoice_due_alerts/static/src/dashboard/traffic_dashboard.scss',
            'gn_invoice_due_alerts/static/src/dashboard/aging_dashboard.scss',
            'gn_invoice_due_alerts/static/src/dashboard/loan_dashboard.scss',
            'gn_invoice_due_alerts/static/src/dashboard/dashboard_utils.js',
            'gn_invoice_due_alerts/static/src/dashboard/dashboard.xml',
            'gn_invoice_due_alerts/static/src/dashboard/traffic_dashboard.xml',
            'gn_invoice_due_alerts/static/src/dashboard/aging_dashboard.xml',
            'gn_invoice_due_alerts/static/src/dashboard/loan_dashboard.xml',
            'gn_invoice_due_alerts/static/src/dashboard/dashboard.js',
            'gn_invoice_due_alerts/static/src/dashboard/traffic_dashboard.js',
            'gn_invoice_due_alerts/static/src/dashboard/aging_dashboard.js',
            'gn_invoice_due_alerts/static/src/dashboard/loan_dashboard.js',
            'gn_invoice_due_alerts/static/src/cxp_partner_list/cxp_partner_list.xml',
            'gn_invoice_due_alerts/static/src/cxp_partner_list/cxp_partner_list.js',
        ],
    },
    'installable': True,
    'application': True,
}
