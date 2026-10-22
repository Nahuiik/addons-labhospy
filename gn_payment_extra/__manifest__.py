# -*- coding: utf-8 -*-
{
    'name': 'GN Payment Extra',
    'version': '19.0.1.2.15',
    'category': 'Accounting',
    'summary': 'Módulo para gestionar periodos extra en pagos con tarjetas de crédito',
    'description': """
        Módulo para gestionar periodos extra en pagos:
        - Identifica diarios tipo banco
        - Agrega campo booleano "Tarjetas de Crédito" en diarios
        - Crea modelo maestro "Extra" para periodos (9 días, 3 días, 30 días, etc.)
        - Muestra campo "Extra" en pagos de facturas de cliente solo si el diario es tipo banco y está marcado como tarjeta de crédito
        - Reporte de Comisiones por POS
    """,
    'author': 'Grupo Nahuiik',
    'website': 'http://odoo.gruponahuiik.com',
    'depends': ['base', 'account', 'gts_multiple_invoice_payment_currency', 'l10n_hn_cash_register', 'report_xlsx'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'report/report_report.xml',
        'report/pos_commission_report_pdf.xml',
        'views/card_agreement_views.xml',
        'views/account_journal_views.xml',
        'views/account_payment_views.xml',
        'views/account_payment_register_views.xml',
        'views/hide_check_fields_views.xml',
        'views/fix_partner_widget_views.xml',
        'views/pos_commission_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

