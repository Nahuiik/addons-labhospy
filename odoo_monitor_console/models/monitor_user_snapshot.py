# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MonitorUserSnapshot(models.Model):
    """Modelo para almacenar snapshots de métricas por instancia"""
    _name = 'monitor.user_snapshot'
    _description = 'Snapshot de Métricas de Usuarios'
    _order = 'snapshot_date desc'

    instance_id = fields.Many2one(
        'monitor.instance',
        string='Instancia',
        required=True,
        index=True,
        ondelete='cascade'
    )
    snapshot_date = fields.Datetime(
        string='Fecha del Snapshot',
        required=True,
        index=True,
        default=fields.Datetime.now
    )
    
    # Totales
    users_total = fields.Integer(string='Total Usuarios')
    users_active = fields.Integer(string='Usuarios Activos')
    users_archived = fields.Integer(string='Usuarios Archivados')
    portal_total = fields.Integer(string='Total Portal')
    internal_total = fields.Integer(string='Total Interno')
    
    # Activos última hora
    active_last_hour_total = fields.Integer(string='Activos Última Hora (Total)')
    active_last_hour_portal = fields.Integer(string='Activos Última Hora (Portal)')
    active_last_hour_internal = fields.Integer(string='Activos Última Hora (Interno)')
    
    # Información de instancia (cache)
    instance_version = fields.Char(string='Versión Instancia')
    instance_db = fields.Char(string='Base de Datos Instancia')

