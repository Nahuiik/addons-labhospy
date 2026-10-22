from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    branch_id = fields.Many2one('res.branch', 'Branch')
    gts_no_exigir_sucursal = fields.Boolean(
        string='Sucursal Opcional',
        default=False,
        help='Si está activo, el campo Sucursal deja de ser obligatorio en este movimiento.',
    )

    def _prepare_procurement_values(self):
        values = super(StockMove, self)._prepare_procurement_values()
        values.update({
            'branch_id': self.branch_id.id,
        })
        return values

    def _get_new_picking_values(self):
        values = super(StockMove, self)._get_new_picking_values()
        values.update({
            'branch_id': self.branch_id.id,
        })
        return values
