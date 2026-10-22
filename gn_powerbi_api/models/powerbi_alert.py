# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PowerBiAlert(models.Model):
    _name = 'powerbi.alert'
    _description = 'Power BI Alert'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
    )
    alert_type = fields.Selection(
        [
            ('export_failed', 'Error de Exportación'),
            ('slow_export', 'Exportación Lenta'),
            ('low_records', 'Bajo Número de Registros'),
            ('connection_error', 'Error de Conexión'),
        ],
        string='Tipo de Alerta',
        required=True,
    )
    date = fields.Datetime(
        string='Fecha',
        required=True,
        default=fields.Datetime.now,
    )
    table_id = fields.Many2one(
        'powerbi.table',
        string='Tabla',
        ondelete='cascade',
    )
    dataset_id = fields.Many2one(
        'powerbi.dataset',
        string='Dataset',
        ondelete='cascade',
    )
    message = fields.Text(
        string='Mensaje',
        required=True,
    )
    notification_method = fields.Selection(
        [
            ('chatter', 'Chatter'),
            ('email', 'Email'),
            ('notification', 'Notificación Interna'),
        ],
        string='Método de Notificación',
        default='chatter',
    )
    user_ids = fields.Many2many(
        'res.users',
        string='Usuarios a Notificar',
    )
    active = fields.Boolean(
        string='Activa',
        default=True,
    )
    resolved = fields.Boolean(
        string='Resuelta',
        default=False,
    )

    def action_resolve(self):
        """Marca la alerta como resuelta"""
        self.write({'resolved': True})

    def action_notify(self):
        """Envía notificaciones según el método configurado"""
        for alert in self:
            if alert.notification_method == 'chatter':
                alert.message_post(
                    body=alert.message,
                    subject=alert.name,
                )
            elif alert.notification_method == 'email':
                # Implementar envío de email
                pass
            elif alert.notification_method == 'notification':
                # Implementar notificación interna
                pass

