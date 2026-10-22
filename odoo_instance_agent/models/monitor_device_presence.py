# -*- coding: utf-8 -*-

import logging
import uuid
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MonitorDevicePresence(models.Model):
    """Modelo para tracking de presencia de dispositivos por usuario"""
    _name = 'monitor.device_presence'
    _description = 'Presencia de Dispositivos'
    _order = 'last_seen desc'
    _rec_name = 'display_name'

    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        index=True,
        ondelete='cascade'
    )
    device_id = fields.Char(
        string='ID de Dispositivo',
        required=True,
        index=True,
        help='UUID único por dispositivo/sesión'
    )
    last_seen = fields.Datetime(
        string='Última Actividad',
        required=True,
        index=True,
        default=fields.Datetime.now
    )
    user_type = fields.Selection(
        [('internal', 'Interno'), ('portal', 'Portal')],
        string='Tipo de Usuario',
        required=True,
        index=True,
        help='Tipo de usuario: Interno o Portal'
    )
    ip_address = fields.Char(string='Dirección IP')
    user_agent = fields.Char(string='User Agent')
    is_archived = fields.Boolean(
        string='Usuario Archivado',
        default=False,
        help='Indica si el usuario está archivado'
    )
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=False
    )

    _unique_device_user = models.Constraint(
        'UNIQUE (device_id, user_id)',
        'Ya existe un registro para este dispositivo y usuario'
    )

    @api.depends('user_id', 'device_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.user_id:
                rec.display_name = f"{rec.user_id.name} - {rec.device_id[:8]}"
            else:
                rec.display_name = rec.device_id

    @api.model
    def register_heartbeat(self, device_id, user_id=None, ip_address=None, user_agent=None):
        """
        Registra o actualiza un heartbeat de dispositivo
        
        :param device_id: UUID del dispositivo
        :param user_id: ID del usuario (si None, usa usuario actual)
        :param ip_address: IP del cliente
        :param user_agent: User agent del navegador
        :return: registro creado/actualizado
        """
        if not user_id:
            user_id = self.env.user.id
        
        if not user_id:
            raise ValidationError(_('No se puede registrar heartbeat sin usuario'))
        
        user = self.env['res.users'].browse(user_id)
        if not user.exists():
            raise ValidationError(_('Usuario no encontrado'))
        
        # Determinar tipo de usuario
        user_type = self._get_user_type(user)
        
        # Buscar registro existente
        presence = self.search([
            ('device_id', '=', device_id),
            ('user_id', '=', user_id)
        ], limit=1)
        
        now_time = fields.Datetime.now()
        vals = {
            'user_id': user_id,
            'device_id': device_id,
            'last_seen': now_time,
            'user_type': user_type,
            'is_archived': not user.active,
            'ip_address': ip_address,
            'user_agent': user_agent,
        }
        
        if presence:
            presence.write(vals)
            _logger.debug(f'Heartbeat actualizado: device={device_id[:8]}..., user={user.login}, last_seen={now_time}')
            return presence
        else:
            new_presence = self.create(vals)
            _logger.info(f'Heartbeat creado: device={device_id[:8]}..., user={user.login}, last_seen={now_time}')
            return new_presence

    @api.model
    def _get_user_type(self, user):
        """
        Determina el tipo de usuario (portal/interno) según versión de Odoo
        
        Estrategia:
        1. Si existe campo 'share', usarlo directamente
        2. Si no, inferir por grupos (portal vs internal)
        """
        # Estrategia 1: Campo 'share' (Odoo 11+)
        if hasattr(user, 'share'):
            return 'portal' if user.share else 'internal'
        
        # Estrategia 2: Inferir por grupos
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if portal_group and user in portal_group.users:
            return 'portal'
        
        # Por defecto, interno
        return 'internal'

    @api.model
    def get_active_users_last_hour(self, window_minutes=60):
        """
        Obtiene usuarios activos en la última hora (ventana configurable)
        
        :param window_minutes: Ventana de tiempo en minutos (default 60)
        :return: dict con estadísticas y lista de usuarios activos
        """
        cutoff_time = fields.Datetime.now() - timedelta(minutes=window_minutes)
        now_time = fields.Datetime.now()
        
        # Obtener dispositivos activos en la ventana
        active_devices = self.search([
            ('last_seen', '>=', cutoff_time)
        ])
        
        # Verificar todos los registros para debugging
        all_devices = self.search([])
        recent_devices = []
        for device in all_devices[:10]:  # Solo primeros 10 para no saturar logs
            if device.last_seen:
                time_diff = (now_time - device.last_seen).total_seconds() / 60
                if time_diff <= window_minutes:
                    recent_devices.append(device)
        
        _logger.info(f'Buscando usuarios activos: window={window_minutes}min, cutoff={cutoff_time}, ahora={now_time}')
        _logger.info(f'Total dispositivos en BD: {len(all_devices)}, encontrados activos: {len(active_devices)}')
        if all_devices:
            sample = all_devices[0]
            _logger.info(f'Ejemplo dispositivo: user={sample.user_id.name if sample.user_id else "None"}, last_seen={sample.last_seen}, diff_minutos={(now_time - sample.last_seen).total_seconds() / 60 if sample.last_seen else "N/A"}')
        
        # Agrupar por usuario
        users_data = {}
        for device in active_devices:
            if not device.user_id:
                _logger.warning(f'Dispositivo sin usuario: {device.device_id}')
                continue
                
            user_id = device.user_id.id
            if user_id not in users_data:
                users_data[user_id] = {
                    'user_id': user_id,
                    'login': device.user_id.login,
                    'name': device.user_id.name,
                    'user_type': device.user_type,
                    'archived': device.is_archived,
                    'last_activity': device.last_seen,
                    'devices_count': 0,
                    'devices': []
                }
            
            users_data[user_id]['devices_count'] += 1
            users_data[user_id]['devices'].append({
                'device_id': device.device_id,
                'last_seen': device.last_seen.isoformat() if device.last_seen else None,
                'ip': device.ip_address,
                'user_agent': device.user_agent
            })
            # Actualizar última actividad si es más reciente
            if device.last_seen > users_data[user_id]['last_activity']:
                users_data[user_id]['last_activity'] = device.last_seen
        
        # Convertir datetime a string ISO para JSON
        result = []
        for user_data in users_data.values():
            user_data_copy = user_data.copy()
            # Convertir last_activity a string ISO
            if isinstance(user_data_copy['last_activity'], (datetime, type(fields.Datetime.now()))):
                user_data_copy['last_activity'] = user_data_copy['last_activity'].isoformat()
            # Remover devices para simplificar (opcional)
            user_data_copy.pop('devices', None)
            result.append(user_data_copy)
        
        _logger.info(f'Usuarios activos encontrados: {len(result)}')
        if result:
            _logger.debug(f'Ejemplo usuario activo: {result[0].get("login")}, devices={result[0].get("devices_count")}, last_activity={result[0].get("last_activity")}')
        return result

    @api.model
    def get_statistics(self, window_minutes=60):
        """
        Obtiene estadísticas completas de usuarios
        
        :param window_minutes: Ventana de tiempo en minutos
        :return: dict con todas las estadísticas
        """
        # Totales de usuarios
        all_users = self.env['res.users'].search([])
        users_total = len(all_users)
        users_active = len(all_users.filtered(lambda u: u.active))
        users_archived = users_total - users_active
        
        # Contar por tipo (usando registros de presencia)
        portal_total = len(self.search([('user_type', '=', 'portal')]).mapped('user_id'))
        internal_total = len(self.search([('user_type', '=', 'internal')]).mapped('user_id'))
        
        # Activos en última hora
        active_last_hour = self.get_active_users_last_hour(window_minutes)
        active_last_hour_total = len(active_last_hour)
        active_last_hour_portal = len([u for u in active_last_hour if u['user_type'] == 'portal'])
        active_last_hour_internal = len([u for u in active_last_hour if u['user_type'] == 'internal'])
        
        _logger.debug(f'Estadísticas: total={active_last_hour_total}, portal={active_last_hour_portal}, internal={active_last_hour_internal}')
        
        return {
            'users_total': users_total,
            'users_active': users_active,
            'users_archived': users_archived,
            'portal_total': portal_total,
            'internal_total': internal_total,
            'active_last_hour_total': active_last_hour_total,
            'active_last_hour_portal': active_last_hour_portal,
            'active_last_hour_internal': active_last_hour_internal,
            'active_users': active_last_hour,
        }

    @api.model
    def cleanup_old_records(self, days=7):
        """
        Limpia registros antiguos (más de N días sin actividad)
        
        :param days: Días de antigüedad para limpiar
        """
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_records = self.search([('last_seen', '<', cutoff_date)])
        count = len(old_records)
        old_records.unlink()
        _logger.info(f'Limpiados {count} registros de presencia antiguos (>{days} días)')
        return count

