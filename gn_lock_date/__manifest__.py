# -*- coding: utf-8 -*-
{
    'name': 'GN Lock Date',
    'version': '19.0.2.0.6',
    'summary': 'Bloqueo de Períodos para Diarios Contables',
    'description': """
GN Lock Date - Bloqueo de Períodos
===================================

Este módulo permite bloquear diarios contables para ciertos períodos de tiempo,
previniendo que los usuarios publiquen transacciones en fechas bloqueadas.

Características principales
---------------------------

* Crear bloqueos de período con fecha desde y fecha hasta
* Seleccionar diarios específicos a bloquear
* Prevenir publicación de movimientos contables en períodos bloqueados
* Opción de desbloqueo para usuarios con permisos especiales
* Validación al crear, modificar o publicar movimientos contables
* Control de acceso mediante grupos de seguridad
* Centro Lock Dates (dashboard OWL) y asistente de fechas nativas CE en ``res.company``
* Vistas de listado para ``account.lock_exception`` (excepciones de fechas de bloqueo CE)
    """,
    'category': 'Accounting',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': ['account', 'mail', 'web'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizards/account_change_lock_date_views.xml',
        'views/lock_dates_dashboard_views.xml',
        'views/account_lock_exception_views.xml',
        'views/gn_period_lock_views.xml',
        'views/lock_dates_menus.xml',
        'views/account_move_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_lock_date/static/src/lock_journal_entries_modal/lock_journal_entries_modal.scss',
            'gn_lock_date/static/src/lock_journal_entries_modal/lock_journal_entries_modal.js',
            'gn_lock_date/static/src/lock_journal_entries_modal/lock_journal_entries_modal.xml',
            'gn_lock_date/static/src/lock_dates_dashboard/lock_dates_dashboard.scss',
            'gn_lock_date/static/src/lock_dates_dashboard/lock_dates_dashboard.js',
            'gn_lock_date/static/src/lock_dates_dashboard/lock_dates_dashboard.xml',
            'gn_lock_date/static/src/lock_dates_wizard/lock_dates_wizard.scss',
            'gn_lock_date/static/src/lock_dates_wizard/lock_dates_wizard.js',
            'gn_lock_date/static/src/account_move_lock_warning/account_move_lock_warning.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
