{
    'name': 'Labhospy Elite Architects API (read-only)',
    'version': '19.0.1.0.1',
    'category': 'Tools',
    'summary': 'Read-only API access group for Elite Architects integration (Appendix A models)',
    'depends': [
        'base',
        'mail',
        'sale',
        'crm',
        'purchase',
        'stock',
        'account',
        'product',
        'uom',
    ],
    'data': [
        'security/gn_labhospy_ea_api_groups.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'license': 'LGPL-3',
    'author': 'Grupo Nahuiik',
}
