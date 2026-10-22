# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PowerBiTable(models.Model):
    _name = 'powerbi.table'
    _description = 'Power BI Table'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
    )
    pbi_table_name = fields.Char(
        string='Nombre en Power BI',
        help='Nombre de la tabla en Power BI (por defecto usa el nombre)',
    )
    dataset_id = fields.Many2one(
        'powerbi.dataset',
        string='Dataset',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Modelo Odoo',
        required=True,
        tracking=True,
        ondelete='cascade',
        help='Modelo de Odoo del cual se exportarán los datos',
    )
    domain = fields.Char(
        string='Dominio',
        default='[]',
        help='Dominio de filtro para seleccionar registros (formato Python)',
    )
    use_cron = fields.Boolean(
        string='Usar Cron',
        default=False,
        tracking=True,
        help='Exportar automáticamente mediante cron',
    )
    cron_mode = fields.Selection(
        [
            ('incremental', 'Incremental'),
            ('full', 'Completo'),
        ],
        string='Modo Cron',
        default='incremental',
        tracking=True,
        help='Modo de exportación para el cron',
    )
    batch_size = fields.Integer(
        string='Tamaño de Lote',
        default=10000,
        tracking=True,
        help='Número de registros por lote en la exportación',
    )
    last_sync_datetime = fields.Datetime(
        string='Última Sincronización',
        readonly=True,
        tracking=True,
        help='Fecha y hora de la última sincronización exitosa',
    )
    last_cron_run = fields.Datetime(
        string='Última Ejecución Cron',
        readonly=True,
        tracking=True,
    )
    last_sync_state = fields.Selection(
        [
            ('never_run', 'Nunca ejecutado'),
            ('success', 'Éxito'),
            ('failed', 'Error'),
            ('no_data', 'Sin datos'),
            ('skipped', 'Omitido'),
        ],
        string='Estado Última Sincronización',
        default='never_run',
        readonly=True,
        tracking=True,
    )
    force_full_export_next_run = fields.Boolean(
        string='Forzar Exportación Completa',
        default=False,
        tracking=True,
        help='Forzar exportación completa en la próxima ejecución',
    )
    field_ids = fields.One2many(
        'powerbi.table.field',
        'table_id',
        string='Campos',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        tracking=True,
    )

    @api.constrains('domain')
    def _check_domain(self):
        """Valida que el dominio sea una lista válida"""
        for record in self:
            if record.domain:
                try:
                    eval(record.domain)
                except Exception:
                    raise ValidationError(_('El dominio debe ser una lista válida de Python'))

    def _prepare_domain(self):
        """
        Prepara el dominio como lista de Python
        """
        self.ensure_one()
        if not self.domain or self.domain == '[]':
            return []
        try:
            return eval(self.domain)
        except Exception as e:
            _logger.error('Error al parsear dominio %s: %s', self.domain, str(e))
            return []

    def _get_records_to_export(self, mode='auto'):
        """
        Obtiene los registros a exportar según el modo
        """
        self.ensure_one()

        if not self.model_id:
            raise UserError(_('Debe seleccionar un modelo de Odoo'))

        model = self.env[self.model_id.model]
        domain = self._prepare_domain()

        # Determinar modo de exportación
        if mode == 'auto':
            if self.force_full_export_next_run or not self.last_sync_datetime:
                mode = 'full'
            else:
                mode = self.cron_mode or 'incremental'

        # Aplicar filtro incremental si corresponde
        if mode == 'incremental' and self.last_sync_datetime:
            use_write_date = self.env['ir.config_parameter'].sudo().get_param(
                'powerbi_use_write_date_default',
                'True'
            ) == 'True'

            incremental_domain = ['|']
            incremental_domain.append(('create_date', '>', self.last_sync_datetime))
            if use_write_date:
                incremental_domain.append(('write_date', '>', self.last_sync_datetime))

            # Combinar con el dominio base
            if domain:
                domain = ['&'] + domain + incremental_domain
            else:
                domain = incremental_domain

        # Obtener registros
        records = model.search(domain)
        return records

    def action_export_manual(self):
        """
        Exporta los datos manualmente
        """
        self.ensure_one()

        # Validaciones
        if not self.dataset_id.pbi_dataset_id:
            raise UserError(_('El dataset debe estar publicado antes de exportar datos'))

        if not self.field_ids.filtered('export'):
            raise UserError(_('Debe configurar al menos un campo para exportar'))

        # Llamar al servicio de exportación
        export_service = self.env['powerbi.export.service']
        mode = 'full' if self.force_full_export_next_run else 'auto'

        try:
            result = export_service.export_table(self, mode)
            self.force_full_export_next_run = False

            message = _('Exportación completada: %d registros exportados') % result.get('count', 0)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Exportación Exitosa'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            error_msg = _('Error al exportar datos: %s') % str(e)
            _logger.error(error_msg)
            self.write({
                'last_sync_state': 'failed',
            })
            raise UserError(error_msg)

    @api.model
    def _cron_export_tables(self):
        """
        Método llamado por el cron para exportar todas las tablas marcadas
        """
        tables = self.search([('use_cron', '=', True)])
        export_service = self.env['powerbi.export.service']

        for table in tables:
            try:
                mode = table.cron_mode or 'incremental'
                if table.force_full_export_next_run:
                    mode = 'full'

                export_service.export_table(table, mode)
                table.write({
                    'last_cron_run': fields.Datetime.now(),
                    'force_full_export_next_run': False,
                })

            except Exception as e:
                _logger.error('Error al exportar tabla %s: %s', table.name, str(e))
                table.write({
                    'last_sync_state': 'failed',
                    'last_cron_run': fields.Datetime.now(),
                })
                # Crear alerta si está configurado
                # self._create_export_alert(table, str(e))
                continue

    def action_create_server_action(self):
        """
        Crea una acción de servidor para exportar registros seleccionados
        """
        self.ensure_one()

        if not self.model_id:
            raise UserError(_('Debe seleccionar un modelo de Odoo'))

        # Buscar si ya existe una acción de servidor
        existing_action = self.env['ir.actions.server'].search([
            ('name', '=', f'Export To Power BI: {self.name}'),
            ('model_id', '=', self.model_id.id),
        ], limit=1)

        if existing_action:
            raise UserError(_('Ya existe una acción de servidor para esta tabla'))

        # Crear acción de servidor
        server_action = self.env['ir.actions.server'].create({
            'name': f'Export To Power BI: {self.name}',
            'model_id': self.model_id.id,
            'binding_model_id': self.model_id.id,
            'binding_view_types': 'list',
            'state': 'code',
            'code': f"""
# Exportar registros seleccionados a Power BI
table = env['powerbi.table'].browse({self.id})
export_service = env['powerbi.export.service']
export_service.export_table(table, mode='full', records=records)
            """,
        })

        message = _('Acción de servidor creada exitosamente')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Acción Creada'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_delete_server_action(self):
        """
        Elimina la acción de servidor asociada
        """
        self.ensure_one()

        if not self.model_id:
            return

        server_action = self.env['ir.actions.server'].search([
            ('name', '=', f'Export To Power BI: {self.name}'),
            ('model_id', '=', self.model_id.id),
        ])

        if server_action:
            server_action.unlink()
            message = _('Acción de servidor eliminada exitosamente')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Acción Eliminada'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                },
            }

