# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    due_alert_enabled = fields.Boolean(
        string='Activar alertas de vencimiento',
        default=True)
    due_alert_days_before = fields.Integer(
        string='Dias de anticipacion',
        default=3,
        help='Numero de dias antes del vencimiento para considerar una '
             'factura como "proxima a vencer" y enviar el recordatorio.')
    due_alert_include_overdue = fields.Boolean(
        string='Incluir vencidas en las alertas',
        default=True,
        help='Si esta activo, las notificaciones y correos tambien resumen '
             'las facturas ya vencidas y no pagadas.')
    due_alert_popup_sticky = fields.Boolean(
        string='Notificacion emergente persistente',
        default=True,
        help='Si esta activo, la notificacion emergente permanece hasta que '
             'el usuario la cierre.')
