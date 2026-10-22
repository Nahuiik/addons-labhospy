# -*- coding: utf-8 -*-
{
    'name': "GN Hospital Product Editable",
    'license': 'OPL-1',
    'support': '',

    'summary': """
        """,

    'description': """
        Hospital Product Editable
    """,

    'author': "Grupo Nahuiik",
    'website': "http://www.gruponahuiik.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Products',
    'images': [],

    'version': '19.0.1.0.0',
    #'currency': 'EUR',
    # any module necessary for this one to work correctly
    'depends': ['base', 'professional_templates', 'acs_hms', 'invoice_with_stock_move'],
    #'external_dependencies': {'python': ['num2words', 'PyPDF2']},

    'data': [
        "security/ir.model.access.csv",
        "data/paperformat.xml",
        "report/account_status.xml",
        "views/view_invoice_inh.xml",
        "views/patient_inh_view.xml",
        "report/summary_invoice.xml",
        "report/report_reports.xml"
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,

}
