from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockLocation(models.Model):
    _inherit = 'stock.location'

    branch_id = fields.Many2one('res.branch', 'Branch')
    gts_no_exigir_sucursal = fields.Boolean(
        string='Sucursal Opcional',
        default=False,
        help='Si está activo, el campo Sucursal deja de ser obligatorio en esta ubicación.',
    )

    @api.constrains('branch_id')
    def _check_branch(self):
        for location in self:
            warehouse_obj = self.env['stock.warehouse']
            warehouse_id = warehouse_obj.search(
                ['|', '|', ('wh_input_stock_loc_id', '=', location.id),
                 ('lot_stock_id', '=', location.id),
                 ('wh_output_stock_loc_id', '=', location.id)])
            for warehouse in warehouse_id:
                if location.branch_id != warehouse.branch_id:
                    raise UserError(_('Configuration error\n You must select same branch on '
                                      'a location which is assigned on the related warehouse'))
