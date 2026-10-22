# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    inv_pay_recovery_good_threshold = fields.Float(
        string='Umbral índice recuperación (bueno %)',
        default=85.0,
        help='Porcentaje mínimo para considerar buena la recuperación de cobranza.',
    )
    inv_pay_recovery_warn_threshold = fields.Float(
        string='Umbral índice recuperación (alerta %)',
        default=65.0,
    )
    inv_pay_punctuality_good_threshold = fields.Float(
        string='Umbral puntualidad (bueno %)',
        default=80.0,
    )
    inv_pay_punctuality_warn_threshold = fields.Float(
        string='Umbral puntualidad (alerta %)',
        default=60.0,
    )
    inv_pay_export_max_sync_rows = fields.Integer(
        string='Máx. filas exportación síncrona',
        default=10000,
    )
    inv_pay_table_page_size = fields.Integer(
        string='Tamaño de página tabla',
        default=50,
    )
    inv_pay_large_dataset_threshold = fields.Integer(
        string='Umbral modo SQL (filas estimadas)',
        default=5000,
        help='Por encima de este volumen estimado se usan consultas agregadas SQL '
             'en lugar de cargar todas las filas en memoria.',
    )
