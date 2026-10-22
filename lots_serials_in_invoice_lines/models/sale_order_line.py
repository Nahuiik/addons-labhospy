from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Editable: el usuario selecciona manualmente los lotes a utilizar
    lot_ids = fields.Many2many('stock.lot', string='Lots / Serials', help='Seleccione los números de serie/lotes a utilizar para esta línea')

    @api.constrains('lot_ids', 'product_id')
    def _check_lot_product(self):
        for line in self:
            if not line.product_id or not line.lot_ids:
                continue
            invalid = line.lot_ids.filtered(lambda l: l.product_id and l.product_id != line.product_id)
            if invalid:
                raise ValidationError(_('Los lotes seleccionados no corresponden al producto de la línea.'))

    @api.onchange('product_id', 'order_id.warehouse_id')
    def _onchange_lot_ids_domain(self):
        for line in self:
            domain = [('product_id', '=', line.product_id.id)] if line.product_id else [('id', '=', 0)]
            if line.order_id and line.order_id.warehouse_id and line.product_id and line.product_id.tracking != 'none':
                stock_location = line.order_id.warehouse_id.lot_stock_id
                if stock_location:
                    Quant = self.env['stock.quant']
                    quants = Quant.search([
                        ('product_id', '=', line.product_id.id),
                        ('location_id', 'child_of', stock_location.id),
                        ('quantity', '>', 0),
                        ('lot_id', '!=', False),
                    ])
                    lot_ids = quants.mapped('lot_id').ids
                    domain = [('id', 'in', lot_ids)]
            return {'domain': {'lot_ids': domain}}

