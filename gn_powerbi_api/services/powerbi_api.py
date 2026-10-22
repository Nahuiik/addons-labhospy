# -*- coding: utf-8 -*-

import logging
import requests
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PowerBiApiService(models.AbstractModel):
    _name = 'powerbi.api.service'
    _description = 'Power BI API Service'

    def _make_request(self, connection, method, endpoint, data=None, params=None):
        """
        Realiza una petición HTTP a la API de Power BI
        """
        token = connection._get_access_token()
        if not token:
            raise UserError(_('No se pudo obtener el token de acceso'))

        url = f"{connection.api_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f'Método HTTP no soportado: {method}')

            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            try:
                error_detail = e.response.json()
                error_message = error_detail.get('error', {}).get('message', e.response.text)
            except:
                error_message = e.response.text
            
            # Log detallado para diagnóstico
            _logger.error('Error HTTP %s en %s %s: %s', status_code, method, url, error_message)
            _logger.error('Response headers: %s', e.response.headers)
            
            # Mensajes de error más específicos según el código HTTP
            if status_code == 401:
                error_msg = _(
                    'Error de autenticación (401). Verifica:\n'
                    '- Que el Client Secret no haya expirado\n'
                    '- Que los permisos Tenant.Read.All y Tenant.ReadWrite.All estén otorgados en Azure AD\n'
                    '- Que el consentimiento del administrador esté otorgado\n'
                    'Detalle: %s'
                ) % error_message
            elif status_code == 403:
                error_msg = _(
                    'Error de permisos (403). Verifica:\n'
                    '- Que las configuraciones de Admin API Settings estén habilitadas en Power BI Admin Portal\n'
                    '- Que la aplicación esté agregada a un grupo de seguridad (si usas grupos específicos)\n'
                    '- Que la aplicación tenga acceso a los workspaces en Power BI\n'
                    'Detalle: %s'
                ) % error_message
            elif status_code == 404:
                error_msg = _('Recurso no encontrado (404). Verifica la URL de la API: %s') % url
            else:
                error_msg = _('Error HTTP %s: %s') % (status_code, error_message)
            
            raise UserError(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = _('Error de conexión: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

    def list_workspaces(self, connection):
        """
        Lista todos los workspaces disponibles en Power BI
        """
        endpoint = '/groups'
        response = self._make_request(connection, 'GET', endpoint)
        return response.get('value', [])

    def create_dataset(self, connection, workspace_id, dataset_name, tables):
        """
        Crea un dataset en Power BI con las tablas especificadas
        
        :param connection: powerbi.connection
        :param workspace_id: ID del workspace en Power BI
        :param dataset_name: Nombre del dataset
        :param tables: Lista de diccionarios con definición de tablas
        :return: Diccionario con la respuesta de Power BI incluyendo el dataset_id
        """
        endpoint = f'/groups/{workspace_id}/datasets'
        data = {
            'name': dataset_name,
            'defaultMode': 'Push',
            'tables': tables,
        }
        return self._make_request(connection, 'POST', endpoint, data=data)

    def create_or_update_table(self, connection, workspace_id, dataset_id, table_name, columns):
        """
        Crea o actualiza una tabla en un dataset
        
        :param connection: powerbi.connection
        :param workspace_id: ID del workspace
        :param dataset_id: ID del dataset
        :param table_name: Nombre de la tabla
        :param columns: Lista de diccionarios con definición de columnas
        :return: Respuesta de Power BI
        """
        endpoint = f'/groups/{workspace_id}/datasets/{dataset_id}/tables'
        data = {
            'name': table_name,
            'columns': columns,
        }
        return self._make_request(connection, 'POST', endpoint, data=data)

    def insert_rows(self, connection, workspace_id, dataset_id, table_name, rows):
        """
        Inserta filas en una tabla de Power BI
        
        :param connection: powerbi.connection
        :param workspace_id: ID del workspace
        :param dataset_id: ID del dataset
        :param table_name: Nombre de la tabla
        :param rows: Lista de diccionarios con los datos de las filas
        :return: Respuesta de Power BI
        """
        endpoint = f'/groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}/rows'
        data = {'rows': rows}
        return self._make_request(connection, 'POST', endpoint, data=data)

    def delete_rows(self, connection, workspace_id, dataset_id, table_name):
        """
        Elimina todas las filas de una tabla
        
        :param connection: powerbi.connection
        :param workspace_id: ID del workspace
        :param dataset_id: ID del dataset
        :param table_name: Nombre de la tabla
        :return: Respuesta de Power BI
        """
        endpoint = f'/groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}/rows'
        return self._make_request(connection, 'DELETE', endpoint)

    def refresh_dataset(self, connection, workspace_id, dataset_id):
        """
        Refresca un dataset (para modo Import)
        
        :param connection: powerbi.connection
        :param workspace_id: ID del workspace
        :param dataset_id: ID del dataset
        :return: Respuesta de Power BI
        """
        endpoint = f'/groups/{workspace_id}/datasets/{dataset_id}/refreshes'
        return self._make_request(connection, 'POST', endpoint)

    def delete_dataset(self, connection, workspace_id, dataset_id):
        """
        Elimina un dataset de Power BI
        
        :param connection: powerbi.connection
        :param workspace_id: ID del workspace
        :param dataset_id: ID del dataset
        :return: Respuesta de Power BI (vacía si es exitoso)
        """
        endpoint = f'/groups/{workspace_id}/datasets/{dataset_id}'
        return self._make_request(connection, 'DELETE', endpoint)

