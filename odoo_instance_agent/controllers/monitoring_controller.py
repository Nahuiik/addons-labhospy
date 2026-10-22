# -*- coding: utf-8 -*-

import logging
import json
import socket
from datetime import datetime
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class MonitoringController(http.Controller):
    """Controlador para endpoints de monitoreo"""

    def _validate_token(self, token=None):
        """
        Valida el token de seguridad para acceso a endpoints
        
        :param token: Token proporcionado en la petición
        :return: True si es válido, False en caso contrario
        """
        if not token:
            token = request.httprequest.headers.get('X-Monitor-Token') or \
                    request.params.get('token')
        
        config_token = request.env['ir.config_parameter'].sudo().get_param('monitor.instance_token')
        
        # Normalizar token vacío
        if token == '' or token is None:
            token = None
        
        # Si no hay token configurado en el sistema, permitir acceso desde LAN
        if not config_token or config_token.strip() == '':
            is_local = self._is_local_network()
            _logger.info(f'Validación sin token: is_local={is_local}, client_ip={request.httprequest.environ.get("REMOTE_ADDR")}')
            return is_local
        
        # Si hay token configurado, debe coincidir
        if not token:
            _logger.debug('Token requerido pero no proporcionado')
            return False
        
        is_valid = token.strip() == config_token.strip()
        if not is_valid:
            _logger.debug(f'Token no coincide: recibido="{token[:10]}...", esperado="{config_token[:10]}..."')
        return is_valid

    def _is_local_network(self):
        """
        Verifica si la petición viene de la red local
        
        :return: True si es red local, False en caso contrario
        """
        try:
            # Obtener IP del cliente desde diferentes fuentes
            client_ip = (
                request.httprequest.environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or
                request.httprequest.environ.get('HTTP_X_REAL_IP') or
                request.httprequest.environ.get('REMOTE_ADDR')
            )
            
            if not client_ip:
                _logger.warning('No se pudo determinar IP del cliente')
                return False
            
            # Normalizar IP (puede venir con puerto)
            if ':' in client_ip and not client_ip.startswith('['):
                client_ip = client_ip.split(':')[0]
            
            # Verificar si es localhost
            if client_ip in ['127.0.0.1', '::1', 'localhost', '0.0.0.0']:
                _logger.debug(f'IP reconocida como localhost: {client_ip}')
                return True
            
            # Verificar si es IP privada (10.x, 172.16-31.x, 192.168.x)
            parts = client_ip.split('.')
            if len(parts) == 4:
                try:
                    first = int(parts[0])
                    second = int(parts[1])
                    if first == 10:
                        _logger.debug(f'IP reconocida como LAN (10.x): {client_ip}')
                        return True
                    if first == 172 and 16 <= second <= 31:
                        _logger.debug(f'IP reconocida como LAN (172.16-31.x): {client_ip}')
                        return True
                    if first == 192 and second == 168:
                        _logger.info(f'IP reconocida como LAN (192.168.x): {client_ip}')
                        return True
                except ValueError:
                    pass
            
            _logger.debug(f'IP del cliente no reconocida como LAN: {client_ip}')
            return False
        except Exception as e:
            _logger.warning(f'Error verificando red local: {e}', exc_info=True)
            return False

    def _get_instance_info(self):
        """
        Obtiene información de la instancia actual
        
        :return: dict con información de la instancia
        """
        import odoo
        
        try:
            hostname = socket.gethostname()
        except:
            hostname = 'unknown'
        
        return {
            'name': request.env.cr.dbname,
            'version': odoo.release.version,
            'db': request.env.cr.dbname,
            'hostname': hostname,
            'timestamp': fields.Datetime.now().isoformat(),
        }

    @http.route('/monitoring/heartbeat', type='http', auth='public', methods=['POST'], csrf=False)
    def heartbeat(self, **kwargs):
        """
        Endpoint para recibir heartbeats de dispositivos
        
        Payload esperado:
        {
            "device_id": "uuid-del-dispositivo",
            "user_id": 123 (opcional, si no se usa el usuario de sesión)
        }
        
        :return: dict con resultado del heartbeat
        """
        try:
            # Obtener datos del request
            # Con type='http', usamos request.get_json_data() o parseamos manualmente
            device_id = None
            user_id = None
            
            # Intentar obtener JSON del body usando método de Odoo
            try:
                json_data = request.get_json_data()
                if isinstance(json_data, dict):
                    device_id = json_data.get('device_id')
                    user_id = json_data.get('user_id')
                    _logger.info(f'Datos obtenidos de get_json_data() - device_id: {device_id}, user_id: {user_id}')
            except (ValueError, AttributeError) as e:
                # Si get_json_data() falla, parsear manualmente del body
                _logger.debug(f'get_json_data() falló: {e}, intentando parsear manualmente')
                if hasattr(request, 'httprequest') and request.httprequest.data:
                    try:
                        body_data = json.loads(request.httprequest.data.decode('utf-8'))
                        if isinstance(body_data, dict):
                            device_id = body_data.get('device_id')
                            user_id = body_data.get('user_id')
                            _logger.info(f'Datos obtenidos del body manualmente - device_id: {device_id}, user_id: {user_id}')
                    except Exception as parse_error:
                        _logger.warning(f'Error parseando body JSON: {parse_error}')
            
            if not device_id:
                _logger.warning(f'No se pudo extraer device_id - kwargs: {kwargs}')
            
            # Validar token - simplificado: siempre permitir desde LAN/localhost
            # Esto permite desarrollo y uso en red local sin configuración
            client_ip = request.httprequest.environ.get('REMOTE_ADDR', '')
            is_local_or_lan = (
                client_ip in ['127.0.0.1', '::1', 'localhost'] or 
                client_ip.startswith('192.168.') or 
                client_ip.startswith('10.') or
                (client_ip.startswith('172.') and len(client_ip.split('.')) > 1 and 
                 16 <= int(client_ip.split('.')[1]) <= 31)
            )
            
            if not is_local_or_lan:
                # Solo validar token si NO es LAN/localhost
                if not self._validate_token():
                    _logger.warning(f'Token rechazado para IP externa: {client_ip}')
                    return request.make_json_response({
                        'success': False,
                        'error': 'Token inválido o acceso denegado'
                    })
            else:
                _logger.info(f'Acceso permitido desde LAN/localhost: {client_ip}')
            
            if not device_id:
                _logger.warning('Heartbeat rechazado: device_id no proporcionado')
                return request.make_json_response({
                    'success': False,
                    'error': 'device_id es requerido'
                })
            
            # Obtener user_id de la sesión si no se proporcionó
            if not user_id and request.session.uid:
                user_id = request.session.uid
                _logger.info(f'user_id obtenido de sesión: {user_id}')
            
            # Obtener IP y User Agent
            ip_address = request.httprequest.environ.get('REMOTE_ADDR')
            user_agent = request.httprequest.environ.get('HTTP_USER_AGENT')
            
            # Registrar heartbeat
            _logger.info(f'Recibiendo heartbeat: device_id={device_id[:8] if device_id else "None"}..., user_id={user_id}')
            presence_model = request.env['monitor.device_presence'].sudo()
            try:
                presence = presence_model.register_heartbeat(
                    device_id=device_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                _logger.info(f'Heartbeat registrado exitosamente: id={presence.id}, last_seen={presence.last_seen}')
                
                return request.make_json_response({
                    'success': True,
                    'device_id': device_id,
                    'last_seen': presence.last_seen.isoformat(),
                    'user_type': presence.user_type,
                })
            except Exception as e:
                _logger.error(f'Error al registrar heartbeat: {e}', exc_info=True)
                return request.make_json_response({
                    'success': False,
                    'error': str(e)
                })
        
        except Exception as e:
            _logger.error(f'Error en heartbeat: {e}', exc_info=True)
            return request.make_json_response({
                'success': False,
                'error': str(e)
            })

    @http.route('/monitoring/users_status', type='http', auth='public', methods=['GET'], csrf=False)
    def users_status(self, **kwargs):
        """
        Endpoint para obtener estado de usuarios
        
        Parámetros:
        - window: minutos de ventana (default: 60)
        - token: token de seguridad (opcional si viene en header)
        - format: json (default) o xml
        
        :return: JSON con estadísticas de usuarios
        """
        try:
            # Validar token
            if not self._validate_token():
                return request.make_response(
                    json.dumps({'error': 'Token inválido o acceso denegado'}),
                    headers=[('Content-Type', 'application/json')],
                    status=403
                )
            
            # Obtener parámetros
            window_minutes = int(kwargs.get('window', 60))
            response_format = kwargs.get('format', 'json')
            
            # Obtener estadísticas
            presence_model = request.env['monitor.device_presence'].sudo()
            stats = presence_model.get_statistics(window_minutes)
            
            _logger.info(f'Endpoint users_status: window={window_minutes}min, active_users={len(stats.get("active_users", []))}, active_total={stats.get("active_last_hour_total", 0)}')
            
            # Información de instancia
            instance_info = self._get_instance_info()
            
            # Construir respuesta
            response_data = {
                'instance': instance_info,
                'window_minutes': window_minutes,
                'totals': {
                    'users_total': stats['users_total'],
                    'users_active': stats['users_active'],
                    'users_archived': stats['users_archived'],
                    'portal_total': stats['portal_total'],
                    'internal_total': stats['internal_total'],
                },
                'active_last_hour': {
                    'total': stats['active_last_hour_total'],
                    'portal': stats['active_last_hour_portal'],
                    'internal': stats['active_last_hour_internal'],
                },
                'active_users': stats['active_users'],
            }
            
            if response_format == 'xml':
                # Implementar formato XML si es necesario
                return request.make_response(
                    json.dumps(response_data),  # Por ahora JSON
                    headers=[('Content-Type', 'application/xml')]
                )
            else:
                return request.make_response(
                    json.dumps(response_data, indent=2),
                    headers=[('Content-Type', 'application/json')]
                )
        
        except Exception as e:
            _logger.error(f'Error en users_status: {e}', exc_info=True)
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    @http.route('/monitoring/health', type='http', auth='public', methods=['GET'], csrf=False)
    def health(self, **kwargs):
        """
        Endpoint simple de salud/healthcheck
        
        :return: JSON con estado básico
        """
        try:
            instance_info = self._get_instance_info()
            return request.make_response(
                json.dumps({
                    'status': 'ok',
                    'instance': instance_info,
                }),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.error(f'Error en health: {e}', exc_info=True)
            return request.make_response(
                json.dumps({'status': 'error', 'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

