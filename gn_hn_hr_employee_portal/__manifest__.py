# -*- coding: utf-8 -*-
{
    'name': 'GN Honduras HR Employee Portal',
    'summary': 'Portal web para empleados (usuarios portal) con solicitudes RRHH',
    'description': """
Portal del Empleado Honduras
=============================

Portal web para empleados (usuarios portal) con:
- Mi Perfil y solicitudes de cambio
- Mis Solicitudes (centro unificado)
- Mis Constancias de trabajo
- Ausencias/Vacaciones (si hr_holidays)
- Asistencias (si hr_attendance)
- Payslips (si hr_payroll)
- Anticipos de salario (solicitud portal → flujo salary.advance / RRHH)
- Vista de jefes: vacaciones del equipo

Desarrollado por Grupo Nahuiik - www.gruponahuiik.com
    """,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'email': 'info@gruponahuiik.com',
    'category': 'Human Resources',
    'version': '19.0.1.0.43',
    'license': 'LGPL-3',
    'depends': [
        'portal',
        'website',
        'hr',
        'base_setup',
        'hr_holidays',
        'hr_attendance',
        'hr_payroll',
        'gn_hr_documents',
        'l10n_hn_hr_payroll',
    ],
    'data': [
        'data/certificate_request_sequence.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'security/certificate_request_multicompany.xml',
        'wizard/gn_hr_employee_portal_invite_wizard_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_leave_portal_backend_views.xml',
        'views/hr_leave_type_views.xml',
        'views/res_config_settings_views.xml',
        'views/gn_hr_profile_change_request_views.xml',
        'views/gn_hr_work_certificate_request_views.xml',
        'views/gn_hr_portal_audit_log_views.xml',
        'views/gn_hr_document_policy_views.xml',
        'views/gn_hr_attendance_correction_request_views.xml',
        'views/portal_team_leaves_new_template.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gn_hn_hr_employee_portal/static/src/css/portal.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
