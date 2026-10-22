# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields,models

class ConfigParameter(models.TransientModel):
    _inherit = 'res.config.settings'

    invoice = fields.Boolean(related='company_id.invoice', readonly=False)
    create_stock_move_or_picking = fields.Selection(related='company_id.create_stock_move_or_picking', readonly=False)
    warehouse_id = fields.Many2one(related='company_id.warehouse_id', readonly=False)
