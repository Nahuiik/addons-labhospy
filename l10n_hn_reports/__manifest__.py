# -*- coding: utf-8 -*-
{
    'name': 'Honduras — Reportes fiscales (SAR / 904)',
    'version': '19.0.1.1.44',
    'category': 'Accounting/Localizations',
    'author': 'Labhospy',
    'summary': 'Formulario 904, libros, cierre ISV, resumen ISR (cuentas), retenciones en otros módulos.',
    'description': (
        'Reportes fiscales Honduras: formulario 904 por casillas SAR, libros de compras y ventas en XLSX, '
        'asistente para asiento de cierre ISV en borrador y sincronización de etiquetas en repartos de impuesto.'
    ),
    'depends': ['web', 'l10n_hn_account', 'bi_financial_reports_comm', 'gts_branch_management'],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/sar_tax_tags_data.xml',
        'views/hn_isv_report_views.xml',
        'views/hn_report_menus.xml',
        'views/hn_libro_report_views.xml',
        'views/hn_libro_dashboard.xml',
        'report/hn_libro_report_qweb.xml',
        'views/hn_reporte_isv_dashboard.xml',
        'views/hn_reporte_isv_wizard_views.xml',
        'report/hn_reporte_isv_report.xml',
        'views/hn_isr_summary_wizard_views.xml',
        'views/hn_retention_report_wizard_views.xml',
        'report/hn_isr_summary_report.xml',
        'views/hn_isv_closing_wizard_views.xml',
        'views/res_company_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
    'test': [
        'account',
        'l10n_hn_dmc',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_hn_reports/static/src/isv_dashboard/**/*.scss',
            'l10n_hn_reports/static/src/isv_dashboard/**/*.js',
            'l10n_hn_reports/static/src/isv_dashboard/**/*.xml',
            'l10n_hn_reports/static/src/libro_dashboard/**/*.scss',
            'l10n_hn_reports/static/src/libro_dashboard/**/*.js',
            'l10n_hn_reports/static/src/libro_dashboard/**/*.xml',
        ],
        'web.report_assets_common': [
            'l10n_hn_reports/static/src/css/nahuiik_reports.scss',
            'l10n_hn_reports/static/src/css/libro_resumen.scss',
            'l10n_hn_reports/static/src/css/isv_decl_report.scss',
        ],
    },
}
