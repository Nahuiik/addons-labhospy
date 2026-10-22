# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.tools.misc import formatLang


class ResCompany(models.Model):
    _inherit = 'res.company'

    gn_due_notif_enabled = fields.Boolean(
        string='Activar tarjetas de vencimiento',
        default=True,
        help='Muestra notificaciones visuales interactivas en tiempo real.')
    gn_due_notif_days_before = fields.Integer(
        string='Dias de anticipacion (tarjetas)',
        default=3,
        help='Dias antes del vencimiento para alerta "proxima a vencer".')
    gn_due_notif_critical_days = fields.Integer(
        string='Dias para deuda critica',
        default=15,
        help='Dias vencidos para clasificar como critica.')
    gn_due_notif_repeat_hours = fields.Integer(
        string='Repetir cada (horas)',
        default=24,
        help='Intervalo minimo entre notificaciones de la misma alerta.')
    gn_due_notif_daily_summary_hour = fields.Float(
        string='Hora resumen diario',
        default=8.0,
        help='Hora preferida para el resumen diario (formato 24h).')
    gn_due_notif_realtime_enabled = fields.Boolean(
        string='Notificaciones en tiempo real',
        default=True)
    gn_due_notif_daily_summary_enabled = fields.Boolean(
        string='Resumen diario por correo',
        default=True,
        help='Complementa el cron existente de correo/resumen.')
    gn_due_notif_sound_enabled = fields.Boolean(
        string='Sonido en alertas',
        default=False)
    gn_due_notif_snooze_days = fields.Integer(
        string='Duracion posponer (dias)',
        default=1)
    gn_due_notif_max_visible_cards = fields.Integer(
        string='Max. tarjetas visibles',
        default=5)
    gn_due_notif_default_responsible_id = fields.Many2one(
        'res.users',
        string='Responsable de pago por defecto',
        domain="[('company_ids', 'in', id)]")
    gn_due_notif_notify_account_admins = fields.Boolean(
        string='Incluir administradores contables',
        default=False)
    gn_due_notif_recipient_user_ids = fields.Many2many(
        'res.users',
        'gn_due_notif_recipient_user_rel',
        'company_id',
        'user_id',
        string='Usuarios destinatarios adicionales')
    gn_due_notif_last_daily_summary_date = fields.Date(
        string='Ultimo resumen diario enviado',
        help='Evita enviar el resumen por correo mas de una vez al dia.')
