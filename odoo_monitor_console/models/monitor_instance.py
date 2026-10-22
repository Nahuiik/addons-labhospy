# -*- coding: utf-8 -*-

import logging
import requests
from datetime import datetime, timedelta
from dateutil import parser
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MonitorInstance(models.Model):
    """Modelo para registrar instancias Odoo remotas"""
    _name = 'monitor.instance'
    _description = 'Instancia Odoo'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de la instancia'
    )
    url = fields.Char(
        string='URL',
        required=True,
        help='URL base de la instancia (ej: http://192.168.1.100:8069)'
    )
    token = fields.Char(
        string='Token de Seguridad',
        required=False,
        help='Token configurado en la instancia remota. Si está vacío, solo se permite acceso desde red local.'
    )
    version = fields.Char(
        string='Versión Odoo',
        readonly=True,
        help='Versión detectada de Odoo'
    )
    db_name = fields.Char(
        string='Base de Datos',
        readonly=True
    )
    hostname = fields.Char(
        string='Hostname',
        readonly=True
    )
    active = fields.Boolean(
        string='Activa',
        default=True,
        help='Si está desactivada, no se sincronizará'
    )
    sync_interval = fields.Integer(
        string='Intervalo de Sincronización (minutos)',
        default=5,
        help='Intervalo en minutos para sincronizar métricas'
    )
    last_sync = fields.Datetime(
        string='Última Sincronización',
        readonly=True
    )
    last_sync_status = fields.Selection(
        [('success', 'Éxito'), ('error', 'Error'), ('never', 'Nunca')],
        string='Estado Última Sincronización',
        default='never',
        readonly=True
    )
    last_sync_error = fields.Text(
        string='Último Error',
        readonly=True
    )
    is_online = fields.Boolean(
        string='En Línea',
        compute='_compute_is_online',
        store=True,
        help='Indica si la instancia está en línea basado en la última sincronización'
    )
    strategy = fields.Selection(
        [('heartbeat', 'Heartbeat Propio'), ('presence', 'Presence de Odoo'), ('mixed', 'Mixto')],
        string='Estrategia',
        default='heartbeat',
        help='Estrategia de monitoreo de la instancia'
    )

    _unique_url = models.Constraint(
        'UNIQUE (url)',
        'Ya existe una instancia con esta URL'
    )

    @api.depends('last_sync', 'last_sync_status', 'sync_interval')
    def _compute_is_online(self):
        for rec in self:
            if rec.last_sync_status == 'success':
                # Considerar online si la última sincronización fue exitosa
                # y fue hace menos de 2 intervalos
                if rec.last_sync:
                    max_age = timedelta(minutes=rec.sync_interval * 2)
                    rec.is_online = (fields.Datetime.now() - rec.last_sync) < max_age
                else:
                    rec.is_online = False
            else:
                rec.is_online = False

    def sync_instance(self):
        """
        Sincroniza métricas desde la instancia remota
        
        :return: dict con resultado de la sincronización
        """
        self.ensure_one()
        
        _logger.info(f'Iniciando sincronización: instancia={self.name}, url={self.url}')
        
        if not self.active:
            _logger.warning(f'Instancia inactiva: {self.name}')
            return {'success': False, 'error': 'Instancia inactiva'}
        
        try:
            # Construir URL del endpoint
            endpoint_url = f"{self.url.rstrip('/')}/monitoring/users_status"
            _logger.debug(f'Llamando endpoint: {endpoint_url}')
            
            # Parámetros
            params = {
                'window': 60,  # Ventana de 60 minutos
            }
            if self.token:
                params['token'] = self.token
            
            # Headers
            headers = {
                'Content-Type': 'application/json'
            }
            if self.token:
                headers['X-Monitor-Token'] = self.token
            
            # Realizar petición
            timeout = 30  # 30 segundos de timeout
            _logger.debug(f'Realizando petición GET: url={endpoint_url}, params={params}, headers={headers}')
            response = requests.get(
                endpoint_url,
                params=params,
                headers=headers,
                timeout=timeout,
                verify=False  # En producción, considerar certificados SSL
            )
            
            _logger.info(f'Respuesta recibida: status={response.status_code}, instancia={self.name}')
            
            if response.status_code == 200:
                data = response.json()
                
                # Actualizar información de instancia
                instance_info = data.get('instance', {})
                self.write({
                    'version': instance_info.get('version', ''),
                    'db_name': instance_info.get('db', ''),
                    'hostname': instance_info.get('hostname', ''),
                    'last_sync': fields.Datetime.now(),
                    'last_sync_status': 'success',
                    'last_sync_error': '',
                })
                
                # Crear snapshot
                self._create_snapshot(data)
                
                # Crear líneas de actividad
                active_users_count = len(data.get('active_users', []))
                _logger.info(f'Sincronización exitosa: instancia={self.name}, usuarios_activos={active_users_count}')
                self._create_activity_lines(data)
                
                return {
                    'success': True,
                    'data': data
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                _logger.error(f'Error HTTP en sincronización: instancia={self.name}, status={response.status_code}, error={error_msg}')
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_sync_status': 'error',
                    'last_sync_error': error_msg,
                })
                return {
                    'success': False,
                    'error': error_msg
                }
        
        except requests.exceptions.Timeout:
            error_msg = 'Timeout al conectar con la instancia'
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_status': 'error',
                'last_sync_error': error_msg,
            })
            return {'success': False, 'error': error_msg}
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f'Error de conexión: {str(e)}'
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_status': 'error',
                'last_sync_error': error_msg,
            })
            return {'success': False, 'error': error_msg}
        
        except Exception as e:
            error_msg = f'Error inesperado: {str(e)}'
            _logger.error(f'Error sincronizando instancia {self.name}: {e}', exc_info=True)
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_status': 'error',
                'last_sync_error': error_msg,
            })
            return {'success': False, 'error': error_msg}

    def _create_snapshot(self, data):
        """
        Crea un snapshot de métricas
        
        :param data: Datos recibidos del endpoint
        """
        totals = data.get('totals', {})
        active_last_hour = data.get('active_last_hour', {})
        instance_info = data.get('instance', {})
        
        snapshot = self.env['monitor.user_snapshot'].create({
            'instance_id': self.id,
            'snapshot_date': fields.Datetime.now(),
            'users_total': totals.get('users_total', 0),
            'users_active': totals.get('users_active', 0),
            'users_archived': totals.get('users_archived', 0),
            'portal_total': totals.get('portal_total', 0),
            'internal_total': totals.get('internal_total', 0),
            'active_last_hour_total': active_last_hour.get('total', 0),
            'active_last_hour_portal': active_last_hour.get('portal', 0),
            'active_last_hour_internal': active_last_hour.get('internal', 0),
            'instance_version': instance_info.get('version', ''),
            'instance_db': instance_info.get('db', ''),
        })
        
        return snapshot

    def _create_activity_lines(self, data):
        """
        Crea líneas de actividad por usuario
        
        :param data: Datos recibidos del endpoint
        """
        active_users = data.get('active_users', [])
        
        # Eliminar líneas antiguas de esta instancia
        cutoff_time = fields.Datetime.now() - timedelta(hours=2)
        old_lines = self.env['monitor.user_activity_line'].search([
            ('instance_id', '=', self.id),
            ('last_activity', '<', cutoff_time)
        ])
        old_lines.unlink()
        
        # Crear nuevas líneas
        _logger.info(f'Creando {len(active_users)} líneas de actividad para instancia {self.name}')
        created_count = 0
        for user_data in active_users:
            try:
                # Convertir last_activity si viene como string
                last_activity = user_data.get('last_activity')
                if isinstance(last_activity, str):
                    try:
                        last_activity = parser.parse(last_activity)
                    except Exception as e:
                        _logger.warning(f'Error parseando last_activity "{last_activity}": {e}')
                        # Usar fecha actual como fallback
                        last_activity = fields.Datetime.now()
                elif last_activity is None:
                    # Si no hay last_activity, usar fecha actual
                    last_activity = fields.Datetime.now()
                
                line_vals = {
                    'instance_id': self.id,
                    'user_login': user_data.get('login', ''),
                    'user_name': user_data.get('name', ''),
                    'user_type': user_data.get('user_type', 'internal'),
                    'archived': user_data.get('archived', False),
                    'last_activity': last_activity,
                    'devices_count': user_data.get('devices_count', 0),
                }
                
                _logger.debug(f'Creando línea de actividad: {line_vals}')
                self.env['monitor.user_activity_line'].create(line_vals)
                created_count += 1
            except Exception as e:
                _logger.error(f'Error creando línea de actividad para usuario {user_data.get("login", "unknown")}: {e}', exc_info=True)
        
        _logger.info(f'Líneas de actividad creadas: {created_count}/{len(active_users)} para instancia {self.name}')

    @api.model
    def sync_all_instances(self):
        """
        Sincroniza todas las instancias activas
        
        Método llamado por el cron
        """
        instances = self.search([('active', '=', True)])
        results = []
        
        for instance in instances:
            try:
                result = instance.sync_instance()
                results.append({
                    'instance': instance.name,
                    'success': result.get('success', False),
                    'error': result.get('error')
                })
            except Exception as e:
                _logger.error(f'Error sincronizando instancia {instance.name}: {e}', exc_info=True)
                results.append({
                    'instance': instance.name,
                    'success': False,
                    'error': str(e)
                })
        
        return results

    def action_test_connection(self):
        """
        Acción para probar conexión con la instancia
        """
        self.ensure_one()
        result = self.sync_instance()
        
        if result.get('success'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión Exitosa'),
                    'message': _('La conexión con %s fue exitosa') % self.name,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error de Conexión'),
                    'message': _('Error: %s') % result.get('error', 'Desconocido'),
                    'type': 'danger',
                    'sticky': True,
                }
            }

