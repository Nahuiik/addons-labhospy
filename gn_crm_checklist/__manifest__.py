# -*- coding: utf-8 -*-
{
    'name': 'GN CRM Checklist',
    'version': '1.0.0',
    'summary': 'Checklist y Aprobación para Leads y Oportunidades CRM',
    'description': """
CRM Checklist para Leads y Oportunidades
=========================================

Este módulo permite crear y gestionar checklists para Leads y Oportunidades en CRM.

Características:
---------------
* Menú separado para crear Checklists para Pipeline/Lead
* Vincular múltiples Checklists con el Pipeline/Lead
* Completar o Cancelar checklists vinculadas del Pipeline/Lead
* Porcentaje de Checklist mostrado con el checklist en Pipeline/Lead
* El porcentaje de Checklist se cuenta basado en el número de checklists completadas del Pipeline/Lead
* El Porcentaje de Checklist también se muestra en la Vista Kanban de Pipeline y Lead
* Control de acceso: Solo usuarios con permisos pueden Completar o Cancelar checklist en Pipeline y Lead
    """,
    'category': 'Sales/CRM',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': ['crm', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/gn_crm_checklist_views.xml',
        'views/crm_lead_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

