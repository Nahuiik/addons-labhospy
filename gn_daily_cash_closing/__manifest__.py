# -*- coding: utf-8 -*-
{
    'name': "GN Cierre de Caja Diario",
    'summary': "Reporte PDF de cierre de caja diario por sucursal",
    'description': """
        Genera un reporte PDF de cierre de caja diario que incluye:
        ventas, ingresos, cobros, anulaciones, tarjetas de crédito,
        remesas, traslados de mercadería y documentos anexos.
    """,
    'author': "Grupo Nahuiik",
    'website': "http://odoo.gruponahuiik.com",
    'category': 'Accounting',
    'version': '19.0.1.60',
    'license': 'LGPL-3',
    'depends': ['account', 'gts_branch_management', 'mail', 'stock', 'sale', 'gts_customer_advance', 'gn_payment_extra', 'order_line_sequences', 'report_xlsx'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'reports/report.xml',
        'reports/cash_closing_template.xml',
        'reports/blind_closing_voucher_template.xml',
        'wizard/cash_closing_wizard_view.xml',
        'wizard/generate_move_wizard_view.xml',
        'wizard/blind_closing_wizard_view.xml',
        'views/gn_cash_closing_views.xml',
        'views/account_journal_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_daily_cash_closing/static/src/css/blind_closing_wizard.css',
        ],
    },
}
