# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Parámetros de Power BI
    powerbi_default_batch_size = fields.Integer(
        string='Tamaño de Lote por Defecto',
        config_parameter='powerbi_default_batch_size',
        default=10000,
    )
    powerbi_default_cron_mode = fields.Selection(
        [
            ('incremental', 'Incremental'),
            ('full', 'Completo'),
        ],
        string='Modo Cron por Defecto',
        config_parameter='powerbi_default_cron_mode',
        default='incremental',
    )
    powerbi_use_write_date_default = fields.Boolean(
        string='Usar write_date en Sincronización Incremental',
        config_parameter='powerbi_use_write_date_default',
        default=True,
    )
    powerbi_slow_export_threshold = fields.Integer(
        string='Umbral de Exportación Lenta (segundos)',
        config_parameter='powerbi_slow_export_threshold',
        default=120,
    )
    powerbi_low_record_threshold = fields.Integer(
        string='Umbral de Bajo Número de Registros',
        config_parameter='powerbi_low_record_threshold',
        default=10,
    )
    powerbi_preview_limit = fields.Integer(
        string='Límite de Vista Previa',
        config_parameter='powerbi_preview_limit',
        default=100,
    )
    powerbi_token_expiration_buffer = fields.Integer(
        string='Buffer de Expiración de Token (segundos)',
        config_parameter='powerbi_token_expiration_buffer',
        default=300,
    )
    powerbi_alert_window_hours = fields.Integer(
        string='Ventana de Alertas (horas)',
        config_parameter='powerbi_alert_window_hours',
        default=24,
    )
    powerbi_enable_auto_alerts = fields.Boolean(
        string='Habilitar Alertas Automáticas',
        config_parameter='powerbi_enable_auto_alerts',
        default=True,
    )
    powerbi_show_advanced_alerts = fields.Boolean(
        string='Mostrar Alertas Avanzadas',
        config_parameter='powerbi_show_advanced_alerts',
        default=False,
    )

