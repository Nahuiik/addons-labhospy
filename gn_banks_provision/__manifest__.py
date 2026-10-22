# -*- coding: utf-8 -*-
{
    'name': 'Provisiones bancarias y diferencial cambiario',
    'category': 'Accounting',
    'version': '19.0.1.0.5',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'summary': 'Provisiones contables (devengo) y ajustes por diferencial cambiario integrados con gn_banks.',
    'license': 'OPL-1',
    'depends': [
        'gn_banks',
        'account',
        'mail',
        'analytic',
        'gts_branch_management',
        'wm_journal_entry_report',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/res_config_settings_view.xml',
        'views/bank_provision_views.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
