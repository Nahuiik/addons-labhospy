# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PowerBiTableTemplate(models.Model):
    _name = 'powerbi.table.template'
    _description = 'Power BI Table Template'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Modelo Odoo',
        required=True,
        ondelete='cascade',
        help='Modelo de Odoo para el cual es esta plantilla',
    )
    is_public = fields.Boolean(
        string='Pública',
        default=False,
        help='Permitir que otros usuarios usen esta plantilla',
    )
    created_by = fields.Many2one(
        'res.users',
        string='Creado por',
        default=lambda self: self.env.user,
        readonly=True,
    )
    times_used = fields.Integer(
        string='Veces Usada',
        default=0,
        readonly=True,
    )
    template_definition = fields.Text(
        string='Definición de Plantilla',
        help='JSON con la configuración completa de la plantilla',
    )
    description = fields.Text(
        string='Descripción',
        help='Descripción de la plantilla y su uso',
    )

    def create_from_table(self, table):
        """
        Crea una plantilla a partir de una tabla existente
        """
        import json

        definition = {
            'model_id': table.model_id.id,
            'domain': table.domain,
            'batch_size': table.batch_size,
            'cron_mode': table.cron_mode,
            'fields': [],
        }

        for field in table.field_ids:
            definition['fields'].append({
                'field_id': field.field_id.id,
                'name': field.name,
                'relation_child_field_id': field.relation_child_field_id.id if field.relation_child_field_id else False,
                'export': field.export,
                'sequence': field.sequence,
            })

        self.create({
            'name': f'Plantilla: {table.name}',
            'model_id': table.model_id.id,
            'template_definition': json.dumps(definition),
        })

    def instantiate(self, dataset, name):
        """
        Crea una tabla a partir de esta plantilla
        """
        import json

        self.ensure_one()

        if not self.template_definition:
            raise UserError(_('La plantilla no tiene definición'))

        definition = json.loads(self.template_definition)

        # Crear tabla
        table = self.env['powerbi.table'].create({
            'name': name,
            'dataset_id': dataset.id,
            'model_id': definition['model_id'],
            'domain': definition.get('domain', '[]'),
            'batch_size': definition.get('batch_size', 10000),
            'cron_mode': definition.get('cron_mode', 'incremental'),
        })

        # Crear campos
        for field_def in definition.get('fields', []):
            self.env['powerbi.table.field'].create({
                'table_id': table.id,
                'field_id': field_def['field_id'],
                'name': field_def['name'],
                'relation_child_field_id': field_def.get('relation_child_field_id') or False,
                'export': field_def.get('export', True),
                'sequence': field_def.get('sequence', 10),
            })

        # Incrementar contador de uso
        self.times_used += 1

        return table

