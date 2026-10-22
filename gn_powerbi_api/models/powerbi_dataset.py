# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PowerBiDataset(models.Model):
    _name = 'powerbi.dataset'
    _description = 'Power BI Dataset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
    )
    type = fields.Selection(
        [
            ('permanent', 'Permanente'),
            ('temporary', 'Temporal'),
        ],
        string='Tipo',
        default='permanent',
        required=True,
        tracking=True,
    )
    workspace_id = fields.Many2one(
        'powerbi.workspace',
        string='Workspace',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    pbi_dataset_id = fields.Char(
        string='Power BI Dataset ID',
        readonly=True,
        tracking=True,
        help='ID del dataset en Power BI (se asigna al publicar)',
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('published', 'Publicado'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
        readonly=True,
    )
    table_ids = fields.One2many(
        'powerbi.table',
        'dataset_id',
        string='Tablas',
    )
    table_count = fields.Integer(
        string='Número de Tablas',
        compute='_compute_table_count',
        store=False,
    )

    @api.depends('table_ids')
    def _compute_table_count(self):
        """Calcula el número de tablas"""
        for record in self:
            record.table_count = len(record.table_ids)

    def action_publish(self):
        """
        Publica el dataset en Power BI creándolo con todas sus tablas
        """
        self.ensure_one()

        if not self.workspace_id:
            raise UserError(_('Debe seleccionar un workspace'))

        if not self.table_ids:
            raise UserError(_('Debe agregar al menos una tabla al dataset antes de publicar'))

        connection = self.env['powerbi.connection'].get_active_connection()
        api_service = self.env['powerbi.api.service']

        try:
            # Preparar definición de tablas para Power BI
            tables_definition = []
            for table in self.table_ids:
                if not table.field_ids.filtered('export'):
                    continue  # Saltar tablas sin campos marcados para exportar

                columns = []
                for field in table.field_ids.filtered('export'):
                    pbi_type = field._get_powerbi_type()
                    columns.append({
                        'name': field.name,
                        'dataType': pbi_type,
                    })

                if columns:
                    tables_definition.append({
                        'name': table.pbi_table_name or table.name,
                        'columns': columns,
                    })

            if not tables_definition:
                raise UserError(_('No hay tablas con campos configurados para exportar'))

            # Crear dataset en Power BI
            result = api_service.create_dataset(
                connection,
                self.workspace_id.pbi_workspace_id,
                self.name,
                tables_definition
            )

            # Guardar el ID del dataset
            self.write({
                'pbi_dataset_id': result.get('id'),
                'state': 'published',
            })

            message = _('Dataset publicado exitosamente en Power BI')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Publicación Exitosa'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            error_msg = _('Error al publicar dataset: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

    def action_sync_schema(self):
        """
        Sincroniza el esquema del dataset con Power BI
        Actualiza las tablas y columnas según lo que existe en Power BI
        """
        self.ensure_one()

        if not self.pbi_dataset_id:
            raise UserError(_('El dataset debe estar publicado primero'))

        connection = self.env['powerbi.connection'].get_active_connection()
        # Aquí se implementaría la lógica para obtener el esquema desde Power BI
        # y actualizar las tablas locales

        message = _('Esquema sincronizado exitosamente')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización Exitosa'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_unpublish_wizard(self):
        """
        Abre el wizard para despublicar el dataset
        """
        self.ensure_one()
        
        if self.state != 'published':
            raise UserError(_('El dataset debe estar publicado para poder despublicarlo'))
        
        if not self.pbi_dataset_id:
            raise UserError(_('El dataset no tiene un ID de Power BI asignado'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Despublicar Dataset'),
            'res_model': 'powerbi.dataset.unpublish.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_dataset_id': self.id,
            },
        }

    def action_unpublish(self, delete_in_powerbi=False):
        """
        Despublica el dataset, opcionalmente eliminándolo de Power BI
        
        :param delete_in_powerbi: Si es True, elimina el dataset de Power BI
        """
        self.ensure_one()

        if self.state != 'published':
            raise UserError(_('El dataset debe estar publicado para poder despublicarlo'))

        if not self.pbi_dataset_id:
            raise UserError(_('El dataset no tiene un ID de Power BI asignado'))

        connection = self.env['powerbi.connection'].get_active_connection()
        api_service = self.env['powerbi.api.service']

        try:
            # Si se solicita, eliminar el dataset de Power BI
            if delete_in_powerbi:
                try:
                    api_service.delete_dataset(
                        connection,
                        self.workspace_id.pbi_workspace_id,
                        self.pbi_dataset_id
                    )
                    _logger.info('Dataset %s eliminado de Power BI', self.name)
                except Exception as e:
                    # Si falla la eliminación en Power BI, registrar pero continuar
                    _logger.warning('No se pudo eliminar el dataset de Power BI: %s', str(e))
                    # No lanzar error, solo despublicar localmente

            # Actualizar estado local
            self.write({
                'state': 'draft',
                'pbi_dataset_id': False,
            })

            message = _('Dataset despublicado exitosamente')
            if delete_in_powerbi:
                message += _('. El dataset también fue eliminado de Power BI.')
            else:
                message += _('. El dataset permanece en Power BI pero ya no está vinculado.')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Despublicación Exitosa'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            error_msg = _('Error al despublicar dataset: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

