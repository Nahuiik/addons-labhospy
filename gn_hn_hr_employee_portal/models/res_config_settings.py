# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    portal_card_profile = fields.Boolean(
        string='Tarjeta: Mi perfil',
        config_parameter='gn_hn_hr_employee_portal.portal_card_profile',
        default=True,
    )
    portal_card_requests = fields.Boolean(
        string='Tarjeta: Mis solicitudes',
        config_parameter='gn_hn_hr_employee_portal.portal_card_requests',
        default=True,
    )
    portal_card_certificates = fields.Boolean(
        string='Tarjeta: Mis constancias',
        config_parameter='gn_hn_hr_employee_portal.portal_card_certificates',
        default=True,
    )
    portal_card_leaves = fields.Boolean(
        string='Tarjeta: Mis ausencias',
        config_parameter='gn_hn_hr_employee_portal.portal_card_leaves',
        default=True,
    )
    portal_card_personal_calendar = fields.Boolean(
        string='Tarjeta: Mi calendario',
        config_parameter='gn_hn_hr_employee_portal.portal_card_personal_calendar',
        default=True,
    )
    portal_card_attendances = fields.Boolean(
        string='Tarjeta: Mis asistencias',
        config_parameter='gn_hn_hr_employee_portal.portal_card_attendances',
        default=True,
    )
    portal_card_payslips = fields.Boolean(
        string='Tarjeta: Mis nóminas',
        config_parameter='gn_hn_hr_employee_portal.portal_card_payslips',
        default=True,
    )
    portal_card_salary_advances = fields.Boolean(
        string='Tarjeta: Anticipos de salario',
        config_parameter='gn_hn_hr_employee_portal.portal_card_salary_advances',
        default=True,
    )
    portal_card_team_leaves = fields.Boolean(
        string='Tarjeta: Ausencias del equipo (jefes)',
        config_parameter='gn_hn_hr_employee_portal.portal_card_team_leaves',
        default=True,
    )
    enable_portal_attendance_punch = fields.Boolean(
        string='Habilitar registro de asistencia desde portal',
        config_parameter='gn_hn_hr_employee_portal.enable_portal_attendance_punch',
        default=False,
    )
    enable_portal_exports = fields.Boolean(
        string='Habilitar exportación CSV desde portal',
        config_parameter='gn_hn_hr_employee_portal.enable_portal_exports',
        default=False,
    )
    enable_team_calendar = fields.Boolean(
        string='Habilitar calendario de equipo para jefes',
        config_parameter='gn_hn_hr_employee_portal.enable_team_calendar',
        default=True,
    )
    enable_portal_leave_attachments = fields.Boolean(
        string='Adjuntos en solicitudes de ausencia',
        config_parameter='gn_hn_hr_employee_portal.enable_portal_leave_attachments',
        default=False,
    )
    max_upload_mb = fields.Integer(
        string='Tamaño máximo de adjuntos (MB)',
        config_parameter='gn_hn_hr_employee_portal.max_upload_mb',
        default=5,
    )
    allowed_mimetypes = fields.Char(
        string='MIME types permitidos (separados por coma)',
        config_parameter='gn_hn_hr_employee_portal.allowed_mimetypes',
        default='application/pdf,image/jpeg,image/png,image/gif',
    )
