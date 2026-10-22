# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PowerBiSyncLog(models.Model):
    _name = 'powerbi.sync.log'
    _description = 'Power BI Sync Log'
    _order = 'sync_datetime desc'

    table_id = fields.Many2one(
        'powerbi.table',
        string='Tabla',
        required=True,
        ondelete='cascade',
        index=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Modelo',
        required=True,
        ondelete='cascade',
    )
    res_id = fields.Integer(
        string='ID de Registro',
        required=True,
        index=True,
    )
    operation = fields.Selection(
        [
            ('export', 'Exportar'),
            ('delete', 'Eliminar'),
            ('update', 'Actualizar'),
        ],
        string='Operación',
        required=True,
    )
    sync_datetime = fields.Datetime(
        string='Fecha de Sincronización',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    state = fields.Selection(
        [
            ('success', 'Éxito'),
            ('failed', 'Error'),
            ('skipped', 'Omitido'),
        ],
        string='Estado',
        required=True,
    )
    message = fields.Text(
        string='Mensaje',
        help='Mensaje detallado sobre la operación',
    )

