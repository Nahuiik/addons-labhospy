# -*- coding: utf-8 -*-
{
    'name': "GN Report Account (Branches)",

    'summary': """Report Accounting Nahuiik Branchs""",

    'description': """
        Report by Nahuiik in branchs
    """,

    'author': "Grupo Nahuiik",
    'website': "http://odoo.gruponahuiik.com",

    'category': 'Uncategorized',
    'version': '19.0.1.3',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'report_xlsx', 'gn_labhospy'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'reports/report.xml',
        # 'views/css_style.xml',
        'wizard/menu_item_nahuiik.xml',
        'wizard/advances_not_applied_wizard_view.xml',
        'wizard/commission_wizard_view.xml',
        'wizard/cust_acc_statement_wizard_view.xml',
        'wizard/purchase_analysis_wizard.xml',
        'wizard/purchase_wizard_view.xml',
        # 'wizard/retention_report_wizard_view.xml',
        'wizard/supplier_account_state_wizard.xml',
        'wizard/overdue_to_pay_wizard_view.xml',
        'wizard/state_result_monthly_wizard.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
