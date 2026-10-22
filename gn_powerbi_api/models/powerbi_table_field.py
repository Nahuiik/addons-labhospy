# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PowerBiTableField(models.Model):
    _name = 'powerbi.table.field'
    _description = 'Power BI Table Field'
    _order = 'sequence, name'

    table_id = fields.Many2one(
        'powerbi.table',
        string='Tabla',
        required=True,
        ondelete='cascade',
        index=True,
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Campo Odoo',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id)]",
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Modelo',
        related='table_id.model_id',
        store=True,
        readonly=True,
    )
    name = fields.Char(
        string='Nombre en Power BI',
        required=True,
        help='Nombre de la columna en Power BI',
    )
    ttype = fields.Selection(
        related='field_id.ttype',
        string='Tipo Técnico',
        store=True,
        readonly=True,
    )
    relation_child_field_id = fields.Many2one(
        'ir.model.fields',
        string='Campo Relacional',
        ondelete='cascade',
        domain="[('model_id', '=', relation_model_id)]",
        help='Campo del modelo relacionado a exportar (ej: name para many2one)',
    )
    relation_model_id = fields.Many2one(
        'ir.model',
        string='Modelo Relacionado',
        compute='_compute_relation_model',
        store=False,
    )
    export = fields.Boolean(
        string='Exportar',
        default=True,
        help='Incluir este campo en la exportación',
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de las columnas en Power BI',
    )

    @api.depends('field_id', 'field_id.relation')
    def _compute_relation_model(self):
        """Calcula el modelo relacionado para campos relacionales"""
        for record in self:
            if record.field_id and record.field_id.relation:
                relation_model = self.env['ir.model'].search([
                    ('model', '=', record.field_id.relation)
                ], limit=1)
                record.relation_model_id = relation_model.id
            else:
                record.relation_model_id = False

    @api.onchange('field_id')
    def _onchange_field_id(self):
        """Actualiza el nombre cuando se selecciona un campo"""
        if self.field_id:
            # Usar la descripción del campo como nombre por defecto
            self.name = self.field_id.field_description or self.field_id.name
            # Si es many2one, sugerir el campo 'name' como relación
            if self.field_id.ttype == 'many2one' and self.field_id.relation:
                relation_model = self.env['ir.model'].search([
                    ('model', '=', self.field_id.relation)
                ], limit=1)
                if relation_model:
                    name_field = self.env['ir.model.fields'].search([
                        ('model_id', '=', relation_model.id),
                        ('name', '=', 'name'),
                    ], limit=1)
                    if name_field:
                        self.relation_child_field_id = name_field.id

    def _get_powerbi_type(self):
        """
        Convierte el tipo de campo de Odoo al tipo de Power BI
        """
        self.ensure_one()

        type_mapping = {
            'integer': 'Int64',
            'float': 'Double',
            'monetary': 'Double',
            'char': 'String',
            'text': 'String',
            'html': 'String',
            'date': 'DateTime',
            'datetime': 'DateTime',
            'boolean': 'Boolean',
            'many2one': 'String',  # Se exporta el valor del campo relacionado
            'one2many': 'String',   # Se exporta como texto
            'many2many': 'String', # Se exporta como texto
            'selection': 'String',
        }

        odoo_type = self.ttype or ''
        return type_mapping.get(odoo_type, 'String')

    def convert_value(self, odoo_value):
        """
        Convierte un valor de Odoo al formato esperado por Power BI
        """
        self.ensure_one()

        if odoo_value is False or odoo_value is None:
            return None

        # Manejar campos relacionales
        if self.ttype == 'many2one' and self.relation_child_field_id:
            if hasattr(odoo_value, self.relation_child_field_id.name):
                return getattr(odoo_value, self.relation_child_field_id.name)
            return str(odoo_value) if odoo_value else None

        # Manejar one2many y many2many
        if self.ttype in ('one2many', 'many2many'):
            if isinstance(odoo_value, models.Model):
                # Convertir a lista de nombres o IDs
                if self.relation_child_field_id:
                    return ', '.join([
                        str(getattr(rec, self.relation_child_field_id.name, ''))
                        for rec in odoo_value
                    ])
                return ', '.join([str(rec.id) for rec in odoo_value])
            return str(odoo_value) if odoo_value else None

        # Manejar fechas
        if self.ttype == 'date' and isinstance(odoo_value, str):
            # Convertir fecha a datetime ISO 8601
            from datetime import datetime
            try:
                dt = datetime.strptime(odoo_value, '%Y-%m-%d')
                return dt.isoformat() + 'Z'
            except:
                return odoo_value

        if self.ttype == 'datetime' and isinstance(odoo_value, str):
            # Ya debería estar en formato ISO, pero asegurarse
            return odoo_value if 'T' in odoo_value else odoo_value

        # Manejar booleanos
        if self.ttype == 'boolean':
            return bool(odoo_value)

        # Manejar numéricos
        if self.ttype in ('integer', 'float', 'monetary'):
            try:
                return float(odoo_value) if odoo_value else 0.0
            except:
                return 0.0

        # Por defecto, convertir a string
        return str(odoo_value)

