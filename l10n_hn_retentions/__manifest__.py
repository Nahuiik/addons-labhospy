# -*- coding: utf-8 -*-
{
    'name': "Retenciones Honduras",

    'summary': "Gestión de retenciones hondureñas en pagos y facturas",

    'description': (
        'Localización de retenciones para Honduras: configurar porcentajes y cuentas, '
        'y aplicar los cálculos en pagos de proveedores o clientes (Odoo 19).'
    ),

    'author': "Nahuiik/Mario Matamoros",
    'website': "http://www.odoo.gruponahuiik.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting/Localizations',
    'version': '19.0.1.0.24',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'gts_multiple_invoice_payment_currency', 'l10n_hn_reports'],

    'external_dependencies': {
        'python': ['xlsxwriter'],
    },

    # always loaded
    'data': [
        'data/retention_tax_tags_data.xml',
        'data/data.xml',
        'data/paperformat.xml',
        'security/ir.model.access.csv',
        'wizard/hn_retention_monthly_wizard_views.xml',
        'views/res_config_settings.xml',
        'views/account_payment_register.xml',
        'views/account_payment.xml',
        'views/account_move.xml',
        'views/account_journal.xml',
        'views/res_partner.xml',
        'views/res_company.xml',
        # "views/css_style.xml",
        'report/retention_voucher.xml',
        'report/report_report.xml',
        'report/hn_retention_monthly_summary_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
