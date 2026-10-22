# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hr_payroll_manager_id = fields.Many2one(
        related='company_id.hr_payroll_manager_id',
        readonly=False,
        domain=[('active', '=', True)],
    )
    hr_payroll_approver_id = fields.Many2one(
        related='company_id.hr_payroll_approver_id',
        readonly=False,
        domain=[('active', '=', True)],
    )
    hr_payroll_reviewer_id = fields.Many2one(
        related='company_id.hr_payroll_reviewer_id',
        readonly=False,
        domain=[('active', '=', True)],
    )
    payroll_auditor_ids = fields.Many2many(
        related='company_id.payroll_auditor_ids',
        readonly=False,
        string='Auditores de Nómina',
        domain=[('active', '=', True)],
    )

    l10n_hn_trial_period_days = fields.Integer(
        related='company_id.l10n_hn_trial_period_days',
        readonly=False,
    )
    l10n_hn_hr_alert_recipient_ids = fields.Many2many(
        related='company_id.l10n_hn_hr_alert_recipient_ids',
        readonly=False,
        string='Receptores de Alertas RRHH (HN)',
        domain=[('active', '=', True)],
    )

    is_microenterprise = fields.Boolean(
        related='company_id.is_microenterprise',
        readonly=False,
    )
    l10n_hn_liquidation_enable_resignation_notice_penalty = fields.Boolean(
        string='Liquidación: permitir descuento renuncia sin preaviso',
        config_parameter='l10n_hn_liquidation.enable_resignation_notice_penalty',
        default=False,
    )

    # Fechas de corte - 1ra quincena (6-5)
    l10n_hn_cutoff_start_day_1 = fields.Integer(
        string='Día Inicio Corte (1ra Quincena)',
        config_parameter='l10n_hn_hr_payroll.cutoff_start_day_1',
        default=6,
        help='Día del mes donde inicia el período de corte para 1ra quincena (ej. 6)',
    )
    l10n_hn_cutoff_end_day_1 = fields.Integer(
        string='Día Fin Corte (1ra Quincena)',
        config_parameter='l10n_hn_hr_payroll.cutoff_end_day_1',
        default=5,
        help='Día del mes donde termina el período de corte para 1ra quincena (ej. 5)',
    )
    l10n_hn_cutoff_from_prev_month_1 = fields.Boolean(
        string='Inicio en Mes Anterior (1ra Quincena)',
        config_parameter='l10n_hn_hr_payroll.cutoff_from_prev_month_1',
        default=True,
        help='Si está activo, el día de inicio aplica al mes anterior',
    )
    # Fechas de corte - 2da quincena (21-20)
    l10n_hn_cutoff_start_day_2 = fields.Integer(
        string='Día Inicio Corte (2da Quincena)',
        config_parameter='l10n_hn_hr_payroll.cutoff_start_day_2',
        default=21,
        help='Día del mes donde inicia el período de corte para 2da quincena (ej. 21)',
    )
    l10n_hn_cutoff_end_day_2 = fields.Integer(
        string='Día Fin Corte (2da Quincena)',
        config_parameter='l10n_hn_hr_payroll.cutoff_end_day_2',
        default=20,
        help='Día del mes donde termina el período de corte para 2da quincena (ej. 20)',
    )
    l10n_hn_cutoff_from_prev_month_2 = fields.Boolean(
        string='Inicio en Mes Anterior (2da Quincena)',
        config_parameter='l10n_hn_hr_payroll.cutoff_from_prev_month_2',
        default=True,
        help='Si está activo, el día de inicio aplica al mes anterior (ej. 21 ene - 20 feb)',
    )

    l10n_hn_incap_payroll_mode = fields.Selection(
        [
            ('complement', 'Complemento (IHSS paga subsidio, empresa paga diferencia)'),
            ('full', 'Empresa paga todo (gestiona reembolso IHSS)'),
        ],
        string='Modo Incapacidad IHSS',
        config_parameter='l10n_hn_hr_payroll.incap_payroll_mode',
        default='complement',
        help='Opción 1: Empresa paga solo el complemento (34%), IHSS paga subsidio (66%). '
             'Opción 2: Empresa paga 100% y gestiona reembolso con IHSS.',
    )

    hn_default_vacation_plan_id = fields.Many2one(
        'gn.hn.vacation.plan',
        string='Plan de vacaciones por defecto',
        related='company_id.hn_default_vacation_plan_id',
        readonly=False,
        help='Plan asignado a empleados que no tienen uno definido',
    )
    hn_paternity_days = fields.Integer(
        string='Días licencia paternidad',
        default=5,
        config_parameter='l10n_hn_hr_payroll.paternity_days',
    )
    hn_bereavement_days = fields.Integer(
        string='Días permiso duelo',
        default=3,
        config_parameter='l10n_hn_hr_payroll.bereavement_days',
    )
    hn_marriage_days = fields.Integer(
        string='Días permiso matrimonio',
        default=3,
        config_parameter='l10n_hn_hr_payroll.marriage_days',
    )
    hn_calamity_days = fields.Integer(
        string='Días permiso calamidad',
        default=3,
        config_parameter='l10n_hn_hr_payroll.calamity_days',
    )
    hn_send_email_on_approve = fields.Boolean(
        string='Enviar email al aprobar vacaciones HN',
        default=False,
        config_parameter='l10n_hn_hr_payroll.send_email_on_approve',
    )
    hn_reminder_days_before = fields.Integer(
        string='Días antes para recordatorio',
        default=3,
        config_parameter='l10n_hn_hr_payroll.reminder_days_before',
        help='Enviar recordatorio X días antes del inicio de vacaciones (0=desactivado)',
    )
    hn_warn_approve_without_constancia = fields.Boolean(
        string='Exigir constancia firmada antes de aprobar',
        default=False,
        config_parameter='l10n_hn_hr_payroll.warn_approve_without_constancia',
        help='Bloquear aprobación de vacaciones HN si no hay constancia firmada',
    )
    hn_max_overlap_pct = fields.Float(
        string='% máximo solapamiento por departamento',
        default=30,
        config_parameter='l10n_hn_hr_payroll.max_overlap_pct',
        help='Mostrar advertencia si el % de ausentes en el departamento supera este valor (0=desactivado)',
    )
    hn_enforce_min_days_approval = fields.Boolean(
        string='Exigir días mínimos de anticipación para aprobar',
        default=True,
        config_parameter='l10n_hn_hr_payroll.enforce_min_days_approval',
        help='Si está activo: aprobar con menos de X días requiere HR Manager y motivo de excepción',
    )
    hn_min_days_before_approval = fields.Integer(
        string='Días mínimos de anticipación',
        default=10,
        config_parameter='l10n_hn_hr_payroll.min_days_before_approval',
        help='Mínimo de días antes del inicio para aprobar sin excepción (solo si la validación está activa)',
    )
    report_pdf_use_loopback_assets = fields.Boolean(
        string='PDF: enlazar assets vía localhost (wkhtmltopdf)',
        default=True,
        config_parameter='report.pdf.use_loopback_assets',
        help='Activo por defecto: al generar PDF, el HTML usa la URL interna del servidor (puerto http_port) '
             'para /web/assets en lugar de web.base.url. Evita Connection refused cuando la URL pública '
             'no es accesible desde el mismo servidor. Desactive solo en despliegues especiales; '
             'o defina el parámetro técnico report.url.',
    )
