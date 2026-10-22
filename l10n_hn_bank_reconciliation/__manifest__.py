# -*- coding: utf-8 -*-
{
    'name': "Bank Reconciliation",
    'summary': "Módulo de Conciliación Bancaria para Honduras",
    'description': """
        Módulo de Conciliación Bancaria para Honduras.
        Permite gestionar la conciliación de cuentas bancarias, 
        configurar secuencias para cheques, transferencias, débitos, créditos y depósitos.
    """,
    'author': "César Alejandro Rodriguez Castillo",
    'category': 'Accounting/Localizations',
    'version': '19.0.1.0.2',
    'depends': [
        'base',
        'account',
        'gn_banks',
        'mail',
    ],
    'data': [
        # Security
        'security/groups.xml',
        'security/ir.model.access.csv',
        # Views
        'views/conciliacion_view.xml',
        'views/bank_reconciliation_line_form_view.xml',
        # Wizard
        'wizard/journal_settings_view.xml',
        # Reports
        'reports/report_report.xml',
        'reports/conciliacion_print.xml',
        'reports/conciliacion_print_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_hn_bank_reconciliation/static/css/style.css',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
