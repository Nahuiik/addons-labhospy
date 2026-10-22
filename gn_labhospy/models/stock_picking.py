from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    gn_labhospy_resolution_ref = fields.Char(
        string='Resolución (SC)',
        copy=False,
        help='Obligatoria en recepciones de compra internacional o con sustancias controladas.',
    )
    gn_labhospy_resolution_mandatory = fields.Boolean(
        compute='_compute_gn_labhospy_resolution_mandatory',
    )

    @api.depends(
        'picking_type_id.code',
        'purchase_id.gn_labhospy_compra_internacional',
        'move_ids.state',
        'move_ids.product_id',
        'move_ids.product_id.product_tmpl_id.gn_labhospy_is_controlled',
    )
    def _compute_gn_labhospy_resolution_mandatory(self):
        for picking in self:
            picking.gn_labhospy_resolution_mandatory = picking._gn_labhospy_requires_resolution()

    def _gn_labhospy_requires_resolution(self):
        self.ensure_one()
        if self.picking_type_id.code != 'incoming':
            return False
        if self.purchase_id and self.purchase_id.gn_labhospy_compra_internacional:
            return True
        moves = self.move_ids.filtered(lambda m: m.state != 'cancel')
        return any(
            m.product_id.product_tmpl_id.gn_labhospy_is_controlled for m in moves
        )

    # def button_validate(self):
    #     if self.env['account.move']._gn_labhospy_enforce_receipt_resolution():
    #         for picking in self:
    #             if picking._gn_labhospy_requires_resolution():
    #                 if not (picking.gn_labhospy_resolution_ref or '').strip():
    #                     raise UserError(_(
    #                         'La resolución es obligatoria para esta recepción (compra internacional o '
    #                         'sustancias controladas). Indique la resolución en la cabecera del albarán.'
    #                     ))
    #     return super().button_validate()
