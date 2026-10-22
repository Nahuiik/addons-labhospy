# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PowerBiMetric(models.Model):
    _name = 'powerbi.metric'
    _description = 'Power BI Metric'
    _order = 'date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
    )
    metric_type = fields.Selection(
        [
            ('export_duration', 'Duración de Exportación'),
            ('export_count', 'Cantidad Exportada'),
            ('export_error', 'Error de Exportación'),
            ('connection_test', 'Prueba de Conexión'),
        ],
        string='Tipo de Métrica',
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
        related='table_id.dataset_id',
        store=True,
    )
    value = fields.Float(
        string='Valor',
        help='Valor numérico de la métrica',
    )
    state = fields.Selection(
        [
            ('success', 'Éxito'),
            ('failed', 'Error'),
            ('warning', 'Advertencia'),
        ],
        string='Estado',
        default='success',
    )
    details = fields.Text(
        string='Detalles',
        help='Información adicional sobre la métrica',
    )

