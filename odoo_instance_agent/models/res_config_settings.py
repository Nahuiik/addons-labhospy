# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    monitor_token = fields.Char(
        string='Token de Monitoreo',
        config_parameter='monitor.instance_token',
        help='Token de seguridad para endpoints de monitoreo'
    )
    monitor_window_minutes = fields.Integer(
        string='Ventana de Actividad (minutos)',
        config_parameter='monitor.window_minutes',
        default=60,
        help='Ventana de tiempo en minutos para considerar usuarios activos'
    )
    monitor_heartbeat_interval = fields.Integer(
        string='Intervalo de Heartbeat (segundos)',
        config_parameter='monitor.heartbeat_interval',
        default=60,
        help='Intervalo en segundos para enviar heartbeat desde el navegador'
    )
    monitor_cleanup_days = fields.Integer(
        string='Días para Limpiar Registros',
        config_parameter='monitor.cleanup_days',
        default=7,
        help='Días de antigüedad para limpiar registros de presencia'
    )
    monitor_strategy = fields.Selection(
        [('heartbeat', 'Heartbeat Propio'), ('presence', 'Presence de Odoo'), ('mixed', 'Mixto')],
        string='Estrategia de Monitoreo',
        config_parameter='monitor.strategy',
        default='heartbeat',
        help='Estrategia para detectar actividad de usuarios'
    )

