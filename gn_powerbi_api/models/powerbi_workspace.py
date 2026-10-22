# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PowerBiWorkspace(models.Model):
    _name = 'powerbi.workspace'
    _description = 'Power BI Workspace'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'is_default desc, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
    )
    pbi_workspace_id = fields.Char(
        string='Power BI Workspace ID',
        required=True,
        tracking=True,
        help='ID del workspace en Power BI',
    )
    is_default = fields.Boolean(
        string='Por Defecto',
        default=False,
        tracking=True,
        help='Workspace por defecto para nuevos datasets',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        tracking=True,
        help='Usuario responsable de este workspace',
    )
    dataset_count = fields.Integer(
        string='Número de Datasets',
        compute='_compute_counts',
        store=False,
    )
    report_count = fields.Integer(
        string='Número de Reportes',
        compute='_compute_counts',
        store=False,
    )
    dashboard_count = fields.Integer(
        string='Número de Dashboards',
        compute='_compute_counts',
        store=False,
    )
    connection_id = fields.Many2one(
        'powerbi.connection',
        string='Conexión',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    dataset_ids = fields.One2many(
        'powerbi.dataset',
        'workspace_id',
        string='Datasets',
    )

    @api.depends('dataset_ids')
    def _compute_counts(self):
        """Calcula contadores de datasets, reportes y dashboards"""
        for record in self:
            record.dataset_count = len(record.dataset_ids)
            # Los reportes y dashboards se obtendrían de la API si fuera necesario
            record.report_count = 0
            record.dashboard_count = 0

    @api.constrains('is_default')
    def _check_default_workspace(self):
        """Solo un workspace puede ser por defecto"""
        for record in self:
            if record.is_default:
                other_defaults = self.search([
                    ('is_default', '=', True),
                    ('id', '!=', record.id),
                ])
                if other_defaults:
                    other_defaults.write({'is_default': False})

    def action_import_from_connection(self):
        """
        Importa workspaces desde la conexión asociada (método de conveniencia)
        """
        self.ensure_one()
        if not self.connection_id:
            raise UserError(_('Este workspace no tiene una conexión asociada'))
        return self.connection_id.action_import_workspaces()

    def action_sync_from_remote(self):
        """
        Sincroniza workspace desde la conexión asociada (método individual)
        """
        return self.action_import_from_connection()

    def action_export_to_powerbi(self):
        """
        Exporta información de workspaces a Power BI (crea/actualiza en Power BI)
        Nota: La API de Power BI no permite crear workspaces directamente,
        solo se pueden actualizar propiedades de workspaces existentes.
        """
        self.ensure_one()
        connection = self.env['powerbi.connection'].get_active_connection()
        
        if not self.pbi_workspace_id:
            raise UserError(_('Este workspace no tiene un ID de Power BI asignado. Debe importarlo primero desde Power BI.'))

        # La API de Power BI no permite crear workspaces directamente
        # Solo podemos verificar que existe y actualizar información local
        api_service = self.env['powerbi.api.service']
        
        try:
            # Verificar que el workspace existe en Power BI
            workspaces = api_service.list_workspaces(connection)
            workspace_found = False
            
            for ws_data in workspaces:
                if ws_data.get('id') == self.pbi_workspace_id:
                    workspace_found = True
                    # Actualizar información local con datos de Power BI
                    self.write({
                        'name': ws_data.get('name', self.name),
                    })
                    break
            
            if not workspace_found:
                raise UserError(_('El workspace con ID %s no existe en Power BI') % self.pbi_workspace_id)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Exportación Exitosa'),
                    'message': _('Workspace verificado y actualizado correctamente'),
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            error_msg = _('Error al exportar workspace: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

