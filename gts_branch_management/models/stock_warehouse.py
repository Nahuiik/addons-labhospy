from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    branch_id = fields.Many2one('res.branch', 'Branch')
    gts_no_exigir_sucursal = fields.Boolean(
        string='Sucursal Opcional',
        default=False,
        help='Si está activo, el campo Sucursal deja de ser obligatorio en este almacén.',
    )
