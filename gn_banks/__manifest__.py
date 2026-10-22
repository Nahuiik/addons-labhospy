# -*- coding: utf-8 -*-
{
    'name': 'Módulo de Bancos',
    'category': 'account',
    'version': '19.0.1.1.17',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'summary': (
        'Débito, crédito, depósitos, cheques y transferencias bancarias.'
    ),
    'license': 'OPL-1',
    'description': """
Registros por naturaleza según débito, crédito, depósitos, cheques,
transferencias y pagos relacionados (LABHOSPY).
    """,
    'depends': [
        'base',
        'account',
        'mail',
        'analytic',
        'wm_journal_entry_report',
    ],
    'external_dependencies': {
        'python': ['num2words'],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',

        'wizard/wizard_plantilla_view.xml',
        'wizard/wizard_create_sequence_view.xml',

        'views/account_journal_view.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/ir_sequence_view.xml',
        'views/credit_debit_view.xml',
        'views/bank_provision_views.xml',
        'views/bank_check_view.xml',
        'views/bank_transfer_view.xml',
        'views/bank_template_view.xml',
        'views/date_filter.xml',

        'wizard/banks_reports_view.xml',

        'views/report_account_journal_entries.xml',
        'views/cheqck_paper_format.xml',
        'views/report_check_print.xml',
        'views/report_desktop_voucher.xml',
        'views/report_deposit_voucher.xml',
        'views/report.xml',

        'data/check_data.xml',
        'views/check_format_view.xml',
        'views/dynamic_check.xml',
        'reports/report_account_payment.xml',
        'reports/report_reports.xml',
        'reports/reporte2.xml',
    ],
    'installable': True,
    'application': True,
}
