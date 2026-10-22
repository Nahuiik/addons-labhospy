# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Factura',
        related='sale_id.invoice_id',
        store=True,
        readonly=True,
        help='Factura asociada al picking desde la orden de venta'
    )
    
    sale_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Asesor',
        related='sale_id.user_id',
        readonly=True,
        store=True,
        help='Vendedor asociado a la orden de venta'
    )

