# -*- coding: utf-8 -*-

from datetime import timedelta
from odoo import api, fields, models


class MonitorUserActivityLine(models.Model):
    """Modelo para almacenar usuarios activos por instancia"""
    _name = 'monitor.user_activity_line'
    _description = 'Línea de Actividad de Usuario'
    _order = 'last_activity desc'

    instance_id = fields.Many2one(
        'monitor.instance',
        string='Instancia',
        required=True,
        index=True,
        ondelete='cascade'
    )
    user_login = fields.Char(
        string='Login',
        required=True,
        index=True
    )
    user_name = fields.Char(string='Nombre')
    user_type = fields.Selection(
        [('internal', 'Interno'), ('portal', 'Portal')],
        string='Tipo',
        required=True,
        index=True
    )
    archived = fields.Boolean(string='Archivado', default=False)
    last_activity = fields.Datetime(
        string='Última Actividad',
        required=True,
        index=True
    )
    devices_count = fields.Integer(
        string='Dispositivos',
        default=0,
        help='Número de dispositivos distintos con actividad'
    )

    @api.model
    def get_consolidated_active_users(self, window_minutes=60):
        """
        Obtiene lista consolidada de usuarios activos de todas las instancias
        
        :param window_minutes: Ventana de tiempo en minutos
        :return: lista de dicts con usuarios activos consolidados
        """
        cutoff_time = fields.Datetime.now() - timedelta(minutes=window_minutes)
        
        # Obtener líneas activas
        lines = self.search([
            ('last_activity', '>=', cutoff_time)
        ])
        
        # Agrupar por login (mismo usuario puede estar en varias instancias)
        users_dict = {}
        for line in lines:
            login = line.user_login
            if login not in users_dict:
                users_dict[login] = {
                    'login': login,
                    'name': line.user_name,
                    'user_type': line.user_type,
                    'archived': line.archived,
                    'instances': [],
                    'total_devices': 0,
                    'last_activity': line.last_activity,
                }
            
            users_dict[login]['instances'].append({
                'instance': line.instance_id.name,
                'devices_count': line.devices_count,
                'last_activity': line.last_activity,
            })
            users_dict[login]['total_devices'] += line.devices_count
            
            # Actualizar última actividad si es más reciente
            if line.last_activity > users_dict[login]['last_activity']:
                users_dict[login]['last_activity'] = line.last_activity
        
        return list(users_dict.values())

    @api.model
    def get_top_users_by_devices(self, limit=10):
        """
        Obtiene ranking de usuarios con más dispositivos
        
        :param limit: Número máximo de usuarios a retornar
        :return: lista de dicts ordenada por número de dispositivos
        """
        cutoff_time = fields.Datetime.now() - timedelta(hours=1)
        
        lines = self.search([
            ('last_activity', '>=', cutoff_time)
        ])
        
        # Agrupar por login y sumar dispositivos
        users_dict = {}
        for line in lines:
            login = line.user_login
            if login not in users_dict:
                users_dict[login] = {
                    'login': login,
                    'name': line.user_name,
                    'user_type': line.user_type,
                    'total_devices': 0,
                    'instances_count': 0,
                }
            
            users_dict[login]['total_devices'] += line.devices_count
            users_dict[login]['instances_count'] += 1
        
        # Ordenar por total_devices y retornar top N
        sorted_users = sorted(
            users_dict.values(),
            key=lambda x: x['total_devices'],
            reverse=True
        )
        
        return sorted_users[:limit]

