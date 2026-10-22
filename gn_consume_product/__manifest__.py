{
    'name': 'Productos de Consumo',
    'version': '19.0.1.0.16',
    'category': 'Inventory',
    'summary': 'Gestión de productos de consumo',
    'description': """
        Módulo para gestionar productos de consumo con las siguientes características:
        * Registro de productos de consumo
        * Gestión de ubicaciones de origen y destino
        * Reportes de consumo
    """,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'depends': [
        'base',
        'mail',
        'stock',
        'account',
        'gn_labhospy',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/consume_product_view.xml',
        # 'reports/consume_report.xml',
        # 'reports/consume_report_template.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
} 
