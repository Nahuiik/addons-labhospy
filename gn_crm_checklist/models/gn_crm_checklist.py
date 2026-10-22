# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class GnCrmChecklist(models.Model):
    _name = 'gn.crm.checklist'
    _description = 'CRM Checklist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
    )
    description = fields.Text(
        string='Descripción',
        tracking=True,
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True,
    )
    item_ids = fields.One2many(
        'gn.crm.checklist.item',
        'checklist_id',
        string='Items del Checklist',
        copy=True,
    )
    item_count = fields.Integer(
        string='Número de Items',
        compute='_compute_item_count',
        store=True,
    )

    @api.depends('item_ids')
    def _compute_item_count(self):
        for record in self:
            record.item_count = len(record.item_ids)

    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.item_count > 0:
                name = f"{name} ({record.item_count} items)"
            result.append((record.id, name))
        return result


class GnCrmChecklistItem(models.Model):
    _name = 'gn.crm.checklist.item'
    _description = 'CRM Checklist Item'
    _order = 'sequence, id'

    checklist_id = fields.Many2one(
        'gn.crm.checklist',
        string='Checklist',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(
        string='Nombre del Item',
        required=True,
    )
    description = fields.Text(
        string='Descripción',
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de visualización del item',
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )


