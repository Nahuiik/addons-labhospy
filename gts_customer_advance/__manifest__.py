# -*- coding: utf-8 -*-
{
    'name': 'Customer Advance Payments',
    'version': '19.0.2.2.68',
    'summary': 'Gestión de anticipos de clientes con reclasificación automática',
    'description': '''
        Módulo de Anticipos de Clientes
        ================================
        
        Permite registrar pagos anticipados de clientes contra una cuenta de pasivo corriente 
        conciliable y aplicar estos anticipos automáticamente a facturas del mismo cliente, 
        realizando la reclasificación contable de pasivo a cuentas por cobrar.
        
        Características:
        -----------------
        • Registro de anticipos de clientes en pagos
        • Detección automática de anticipos disponibles en facturas
        • Aplicación de anticipos con wizard interactivo
        • Aplicación desde el anticipo a múltiples facturas
        • Reclasificación automática de pasivo a CxC
        • Conciliación automática al aplicar anticipos
        • Soporte multi-moneda
        • Soporte multi-compañía con reglas de registro
        • Trazabilidad completa en chatter
        • Configuración flexible desde ajustes
        • Filtros de búsqueda para anticipos
        • Menú dedicado para anticipos de clientes
        
        Optimizaciones v2.0:
        ======================
        • Campo advance_available_amount almacenado para filtros SQL
        • Reglas de registro multi-compañía
        • Centralización de obtención de configuración
        • Validaciones mejoradas (factura pagada, cuenta AR)
        • Tracking en campos importantes
        • Reversión de anticipos con trazabilidad
        • Documentación completa con docstrings
    ''',
    'author': 'Geo Technosoft',
    'website': 'http://www.geotechnosoft.com',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['account', 'sale', 'web', 'gts_branch_management', 'gn_payment_extra', 'gts_multiple_invoice_payment_currency'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/account_advance_data.xml',
        'data/advance_sequences.xml',
        'report/advance_payment_report.xml',
        'views/res_config_settings_views.xml',
        'views/account_payment_views.xml',
        'views/account_payment_kanban_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/account_advance_link_views.xml',
        'views/sale_order_views.xml',
        'wizard/apply_advance_wizard_views.xml',
        'wizard/link_advance_wizard_views.xml',
        'wizard/generate_quotas_wizard_views.xml',
        'wizard/advance_report_wizard_views.xml',
        'wizard/reverse_advance_wizard_views.xml',
        'views/advance_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gts_customer_advance/static/src/advance_dashboard/**/*.js',
            'gts_customer_advance/static/src/advance_dashboard/**/*.xml',
            'gts_customer_advance/static/src/advance_dashboard/**/*.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
