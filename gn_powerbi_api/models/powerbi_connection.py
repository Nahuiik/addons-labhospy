# -*- coding: utf-8 -*-

import logging
import requests
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PowerBiConnection(models.Model):
    _name = 'powerbi.connection'
    _description = 'Power BI Connection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'active desc, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
    )
    api_url = fields.Char(
        string='API URL',
        default='https://api.powerbi.com/v1.0/myorg',
        required=True,
        tracking=True,
        help='URL base de la API de Power BI',
    )
    auth_url = fields.Char(
        string='Auth URL',
        default='https://login.microsoftonline.com',
        required=True,
        tracking=True,
        help='URL de autorización de Azure AD',
    )
    tenant_id = fields.Char(
        string='Tenant ID',
        required=True,
        tracking=True,
        help='ID del tenant de Azure AD (Directory ID). '
             'Se encuentra en: Azure Portal > Azure AD > App registrations > Tu app > Overview',
    )
    client_id = fields.Char(
        string='Client ID',
        required=True,
        tracking=True,
        help='ID de la aplicación en Azure AD (Application ID). '
             'Se encuentra en: Azure Portal > Azure AD > App registrations > Tu app > Overview',
    )
    client_secret = fields.Char(
        string='Client Secret',
        required=True,
        tracking=True,
        help='Secret de la aplicación en Azure AD. '
             'Se crea en: Azure Portal > Azure AD > App registrations > Tu app > Certificates & secrets. '
             'IMPORTANTE: También necesitas configurar permisos en Azure AD y agregar la app a los workspaces en Power BI. '
             'Ver documentación completa en: docs/AZURE_AD_SETUP.md',
    )
    redirect_uri = fields.Char(
        string='Redirect URI',
        tracking=True,
        help='URI de redirección configurado en Azure AD',
    )
    access_token = fields.Text(
        string='Access Token',
        readonly=True,
        help='Token de acceso actual (no visible en formulario)',
    )
    refresh_token = fields.Text(
        string='Refresh Token',
        readonly=True,
        help='Token de refresco (no visible en formulario)',
    )
    token_expiration = fields.Datetime(
        string='Token Expiration',
        readonly=True,
        help='Fecha y hora de expiración del token',
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('connected', 'Conectado'),
            ('failed', 'Error'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
        readonly=True,
    )
    active = fields.Boolean(
        string='Activa',
        default=False,
        tracking=True,
        help='Solo una conexión puede estar activa a la vez',
    )
    last_test_message = fields.Text(
        string='Último Mensaje de Prueba',
        readonly=True,
        help='Mensaje de la última prueba de conexión',
    )
    last_test_date = fields.Datetime(
        string='Última Prueba',
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario Asociado',
        tracking=True,
        help='Usuario de Odoo asociado a esta conexión (para documentación y filtrado). '
             'No se usa para autenticación, ya que se usa Client Credentials.',
    )
    workspace_filter_name = fields.Char(
        string='Filtrar Workspaces por Nombre',
        tracking=True,
        help='Filtro opcional para importar solo workspaces cuyo nombre contenga este texto. '
             'Dejar vacío para importar todos los workspaces disponibles.',
    )
    workspace_filter_type = fields.Selection(
        [
            ('all', 'Todos'),
            ('MyWorkspace', 'Solo My Workspace'),
            ('Workspace', 'Solo Workspaces'),
            ('PersonalGroup', 'Solo Grupos Personales'),
        ],
        string='Filtrar por Tipo',
        default='all',
        tracking=True,
        help='Filtro por tipo de workspace. "Todos" importa todos los tipos.',
    )

    @api.constrains('active')
    def _check_active_connection(self):
        """Solo una conexión puede estar activa a la vez"""
        for record in self:
            if record.active:
                # Desactivar otras conexiones activas
                other_connections = self.search([
                    ('active', '=', True),
                    ('id', '!=', record.id),
                ])
                if other_connections:
                    other_connections.write({'active': False})
                    _logger.info(
                        'Desactivadas %d conexiones activas al activar %s',
                        len(other_connections),
                        record.name
                    )

    def _get_access_token(self, force_refresh=False):
        """
        Obtiene o renueva el token de acceso de Azure AD
        """
        self.ensure_one()

        # Verificar si el token actual es válido
        if not force_refresh and self.access_token and self.token_expiration:
            buffer_seconds = int(
                self.env['ir.config_parameter'].sudo().get_param(
                    'powerbi_token_expiration_buffer',
                    '300'
                )
            )
            expiration_buffer = timedelta(seconds=buffer_seconds)
            if datetime.now() < self.token_expiration - expiration_buffer:
                return self.access_token

        # Obtener nuevo token
        token_url = f"{self.auth_url}/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://analysis.windows.net/powerbi/api/.default',
            'grant_type': 'client_credentials',
        }

        try:
            response = requests.post(token_url, data=data, timeout=30)
            response.raise_for_status()
            token_data = response.json()

            access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)

            if access_token:
                expiration = datetime.now() + timedelta(seconds=expires_in)
                self.write({
                    'access_token': access_token,
                    'token_expiration': expiration,
                    'state': 'connected',
                })
                _logger.info('Token obtenido exitosamente para conexión %s', self.name)
                return access_token
            else:
                raise UserError(_('No se recibió access_token en la respuesta'))

        except requests.exceptions.RequestException as e:
            error_msg = _('Error al obtener token: %s') % str(e)
            _logger.error(error_msg)
            self.write({
                'state': 'failed',
                'last_test_message': error_msg,
            })
            raise UserError(error_msg)

    def action_test_connection(self):
        """
        Prueba la conexión con Power BI obteniendo un token y listando workspaces
        """
        self.ensure_one()

        try:
            # Obtener token
            _logger.info('Probando conexión para %s', self.name)
            token = self._get_access_token(force_refresh=True)
            if not token:
                raise UserError(_('No se pudo obtener el token de acceso'))

            # Probar listando workspaces
            api_service = self.env['powerbi.api.service']
            workspaces = api_service.list_workspaces(self)
            
            workspace_count = len(workspaces)
            _logger.info('Conexión exitosa. Se encontraron %d workspace(s)', workspace_count)

            if workspace_count == 0:
                warning_msg = _(
                    'Conexión exitosa, pero no se encontraron workspaces.\n\n'
                    'Esto puede significar que:\n'
                    '1. La aplicación no tiene acceso a ningún workspace en Power BI\n'
                    '2. Las configuraciones de Admin API Settings no están habilitadas\n'
                    '3. La aplicación no está agregada a ningún workspace\n\n'
                    'Verifica la configuración siguiendo la guía en docs/AZURE_AD_SETUP.md'
                )
                self.write({
                    'state': 'connected',
                    'last_test_message': warning_msg,
                    'last_test_date': fields.Datetime.now(),
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Conexión Exitosa (Sin Workspaces)'),
                        'message': warning_msg,
                        'type': 'warning',
                        'sticky': True,
                    },
                }

            success_msg = _(
                'Conexión exitosa. Se encontraron %d workspace(s).'
            ) % workspace_count

            self.write({
                'state': 'connected',
                'last_test_message': success_msg,
                'last_test_date': fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión Exitosa'),
                    'message': success_msg,
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            error_msg = _('Error al probar conexión: %s') % str(e)
            _logger.error('Error al probar conexión %s: %s', self.name, str(e), exc_info=True)
            self.write({
                'state': 'failed',
                'last_test_message': error_msg,
                'last_test_date': fields.Datetime.now(),
            })
            raise UserError(error_msg)

    def _filter_workspaces(self, workspaces):
        """
        Filtra workspaces según los criterios configurados en la conexión
        """
        filtered = []
        
        for ws_data in workspaces:
            # Filtro por nombre
            if self.workspace_filter_name:
                name = ws_data.get('name', '').lower()
                filter_name = self.workspace_filter_name.lower()
                if filter_name not in name:
                    continue
            
            # Filtro por tipo
            if self.workspace_filter_type != 'all':
                ws_type = ws_data.get('type', '')
                if self.workspace_filter_type == 'MyWorkspace' and ws_type != 'MyWorkspace':
                    continue
                elif self.workspace_filter_type == 'Workspace' and ws_type != 'Workspace':
                    continue
                elif self.workspace_filter_type == 'PersonalGroup' and ws_type != 'PersonalGroup':
                    continue
            
            filtered.append(ws_data)
        
        return filtered

    def action_import_workspaces(self):
        """
        Importa workspaces desde Power BI para esta conexión
        Aplica los filtros configurados si existen.
        
        Nota: Con autenticación Client Credentials, la aplicación tiene acceso
        a todos los workspaces según los permisos configurados en Azure AD.
        Los filtros permiten seleccionar qué workspaces importar.
        """
        self.ensure_one()
        api_service = self.env['powerbi.api.service']
        workspace_model = self.env['powerbi.workspace']

        try:
            # Obtener token si no está disponible
            token = self._get_access_token()
            if not token:
                raise UserError(_('No se pudo obtener el token de acceso'))

            # Listar workspaces desde Power BI
            _logger.info('Intentando listar workspaces para conexión %s', self.name)
            all_workspaces = api_service.list_workspaces(self)
            _logger.info('Se encontraron %d workspace(s) en Power BI', len(all_workspaces))
            
            # Log de los workspaces encontrados para diagnóstico
            if all_workspaces:
                workspace_names = [ws.get('name', 'Sin nombre') for ws in all_workspaces[:5]]
                _logger.info('Primeros workspaces encontrados: %s', ', '.join(workspace_names))
            
            # Aplicar filtros
            workspaces = self._filter_workspaces(all_workspaces)
            
            total_found = len(all_workspaces)
            filtered_count = len(workspaces)
            
            _logger.info('Después de aplicar filtros: %d workspace(s) disponibles', filtered_count)
            
            if filtered_count == 0:
                if total_found == 0:
                    # No se encontraron workspaces - proporcionar guía de solución
                    troubleshooting_msg = _(
                        'No se encontraron workspaces disponibles.\n\n'
                        'Posibles causas y soluciones:\n'
                        '1. La aplicación no tiene acceso a ningún workspace:\n'
                        '   - Ve a Power BI Service > Workspace > ... > Workspace access\n'
                        '   - Agrega tu aplicación (Object ID) como miembro del workspace\n\n'
                        '2. Las configuraciones de Admin API Settings no están habilitadas:\n'
                        '   - Ve a Power BI Admin Portal > Tenant settings > Admin API settings\n'
                        '   - Habilita "Service principals can access read-only admin APIs"\n'
                        '   - Habilita "Service principals can access admin APIs used for updates"\n\n'
                        '3. Si usas grupos específicos, verifica que:\n'
                        '   - La aplicación esté en el grupo de seguridad correcto\n'
                        '   - El grupo tenga acceso habilitado en Admin API settings\n\n'
                        '4. Los permisos en Azure AD no están otorgados:\n'
                        '   - Verifica que Tenant.Read.All y Tenant.ReadWrite.All tengan consentimiento del administrador\n\n'
                        '5. Espera 15 minutos después de hacer cambios (tiempo de propagación)'
                    )
                    raise UserError(troubleshooting_msg)
                else:
                    # Hay workspaces pero los filtros los excluyen
                    filter_info = []
                    if self.workspace_filter_name:
                        filter_info.append(_('nombre contiene: "%s"') % self.workspace_filter_name)
                    if self.workspace_filter_type != 'all':
                        filter_info.append(_('tipo: %s') % self.workspace_filter_type)
                    
                    filter_str = ' y '.join(filter_info) if filter_info else _('filtros configurados')
                    
                    # Listar algunos nombres de workspaces encontrados para ayudar al usuario
                    workspace_names = [ws.get('name', 'Sin nombre') for ws in all_workspaces[:10]]
                    names_list = '\n- '.join(workspace_names)
                    if len(all_workspaces) > 10:
                        names_list += _('\n... y %d más') % (len(all_workspaces) - 10)
                    
                    raise UserError(_(
                        'No se encontraron workspaces que coincidan con los filtros configurados.\n\n'
                        'Se encontraron %d workspace(s) en total, pero ninguno pasó los filtros (%s).\n\n'
                        'Workspaces encontrados:\n- %s\n\n'
                        'Sugerencia: Ajusta los filtros en la configuración de la conexión o elimínalos para importar todos los workspaces.'
                    ) % (total_found, filter_str, names_list))
            
            created_count = 0
            updated_count = 0
            error_count = 0

            for ws_data in workspaces:
                try:
                    workspace_id = ws_data.get('id')
                    name = ws_data.get('name', 'Sin nombre')
                    
                    if not workspace_id:
                        _logger.warning('Workspace sin ID encontrado: %s', ws_data)
                        error_count += 1
                        continue

                    existing = workspace_model.search([
                        ('pbi_workspace_id', '=', workspace_id),
                        ('connection_id', '=', self.id),
                    ], limit=1)

                    vals = {
                        'name': name,
                        'pbi_workspace_id': workspace_id,
                        'connection_id': self.id,
                    }

                    if existing:
                        existing.write(vals)
                        updated_count += 1
                    else:
                        workspace_model.create(vals)
                        created_count += 1
                except Exception as e:
                    _logger.error('Error procesando workspace %s: %s', ws_data.get('name', 'Unknown'), str(e))
                    error_count += 1

            if error_count > 0:
                message = _(
                    'Importación completada: %d creados, %d actualizados, %d errores. '
                    'Total encontrados: %d, Filtrados: %d'
                ) % (created_count, updated_count, error_count, total_found, filtered_count)
            else:
                message = _(
                    'Importación completada: %d creados, %d actualizados. '
                    'Total encontrados: %d, Filtrados: %d'
                ) % (created_count, updated_count, total_found, filtered_count)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Importación Exitosa'),
                    'message': message,
                    'type': 'success' if error_count == 0 else 'warning',
                    'sticky': False,
                },
            }

        except Exception as e:
            error_msg = _('Error al importar workspaces: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

    @api.model
    def get_active_connection(self):
        """
        Retorna la conexión activa o lanza excepción si no hay ninguna
        """
        connection = self.search([('active', '=', True)], limit=1)
        if not connection:
            raise UserError(_('No hay ninguna conexión Power BI activa. Por favor configure una conexión.'))
        return connection

