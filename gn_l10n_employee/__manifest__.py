# -*- coding: utf-8 -*-
{
    'name': "GN Constancia de Empleo",
    'version': '19.0.1.0.0',
    'category': 'Payroll',
    'summary': "Constancia de empleo y reportes personalizados para contratos",
    'description': "Extiende contratos para emitir constancias laborales y cálculo de importes en palabras.",
    'license': 'LGPL-3',
    'author': "Grupo Nahuiik",
    'website': "http://www.gruponahuiik.com",
    'depends': [
        'hr',
        'hr_contract',
        'hr_payroll',
        'l10n_hn_hr_payroll',
        'l10n_hn_hr_recruitment',
    ],
    'external_dependencies': {
        'python': ['bs4', 'num2words'],
    },
    'data': [
        'security/groups.xml',
        'views/hr_contract.xml',
        'reports/report.xml',
        'reports/hr_contract_employee_declaration.xml',
        'reports/hr_contract_employee_cancelled_declaration.xml',
    ],
    'installable': True,
    'application': False,
}
