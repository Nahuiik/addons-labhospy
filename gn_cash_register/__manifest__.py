
{
    'name': "CASH REGISTER PDF",
    'author': 'Grupo Nahuiik',
    'category': 'account_invoicing',
    'summary': """Report for customer's outstanding invoice amount within the particular date period""",
    'website': 'http://www.gruponahuiik.com',
    'license': 'AGPL-3',
    'description': """
""",
    'version': '1.0',
    'depends': ['base','account_invoicing'],
    'data': [
        'security/security.xml',
        'wizard/invoice_outstanding.xml',
        'views/invoice_outstanding_report_view.xml',
        'report/invoice_outstanding_template.xml',
        'report/invoice_outstanding_report.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
