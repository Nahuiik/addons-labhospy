# -*- coding: utf-8 -*-
{
    'name': 'Power BI Connector',
    'version': '19.0.1.0.0',
    'category': 'Business Intelligence',
    'summary': 'Integración completa con Microsoft Power BI para Odoo 19',
    'description': """
Power BI Connector para Odoo 19
================================

Este módulo permite integrar Odoo 19 con Microsoft Power BI, proporcionando:

* Configuración de conexión segura con Azure AD OAuth2
* Administración de Workspaces, Datasets y Tablas de Power BI
* Exportación manual y automática de datos desde cualquier modelo de Odoo
* Sincronización incremental basada en create_date y write_date
* Gestión de plantillas de tablas y clonado de configuraciones
* Métricas, logs y alertas para monitoreo
* Monitor de salud en tiempo real
* Versionado de esquemas de datasets y tablas

Desarrollado por Grupo Nahuiik.
    """,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.nahuiik.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'data/ir_model_data.xml',
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        'views/powerbi_connection_views.xml',
        'views/powerbi_workspace_views.xml',
        'views/powerbi_dataset_views.xml',
        'views/powerbi_dataset_unpublish_wizard_views.xml',
        'views/powerbi_table_views.xml',
        'views/powerbi_template_views.xml',
        'views/powerbi_metric_views.xml',
        'views/powerbi_alert_views.xml',
        'views/powerbi_sync_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}

