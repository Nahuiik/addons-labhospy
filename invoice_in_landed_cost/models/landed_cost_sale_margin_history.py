# -*- coding: utf-8 -*-

from odoo import fields, models


class LandedCostSaleMarginHistory(models.Model):
    _name = 'landed.cost.sale.margin.history'
    _description = 'Histórico aplicación margen venta (costeo en destino)'
    _order = 'applied_on desc, id desc'

    landed_cost_id = fields.Many2one(
        'stock.landed.cost',
        string='Costeo en destino',
        required=True,
        ondelete='cascade',
        index=True,
    )
    applied_on = fields.Datetime(
        string='Fecha aplicación',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    applied_by_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        readonly=True,
    )
    global_margin_percent = fields.Float(
        string='% Margen global (asistente)',
        digits=(16, 4),
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='landed_cost_id.company_id.currency_id',
        string='Moneda',
        readonly=True,
    )
    line_ids = fields.One2many(
        'landed.cost.sale.margin.history.line',
        'history_id',
        string='Detalle por producto',
    )


class LandedCostSaleMarginHistoryLine(models.Model):
    _name = 'landed.cost.sale.margin.history.line'
    _description = 'Línea histórico margen venta costeo'
    _order = 'history_id desc, sequence, id'

    history_id = fields.Many2one(
        'landed.cost.sale.margin.history',
        string='Aplicación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    currency_id = fields.Many2one(
        related='history_id.currency_id',
        string='Moneda',
        readonly=True,
    )
    product_id = fields.Many2one('product.product', string='Producto', required=True, readonly=True)
    quantity = fields.Float(string='Cantidad', digits=(16, 4), readonly=True)
    unit_cost = fields.Float(string='Costo unitario final', digits='Product Price', readonly=True)
    price_before_apply = fields.Float(string='PVP anterior', digits='Product Price', readonly=True)
    margin_percent = fields.Float(string='% Margen', digits=(16, 4), readonly=True)
    price_target = fields.Float(string='PVP objetivo', digits='Product Price', readonly=True)
    price_applied = fields.Float(string='PVP aplicado', digits='Product Price', readonly=True)
