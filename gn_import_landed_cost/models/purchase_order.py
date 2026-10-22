from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    gn_import_split_available = fields.Boolean(
        compute='_compute_gn_import_split_available',
    )

    @api.depends(
        'state',
        'gn_labhospy_compra_internacional',
        'picking_ids.state',
        'picking_ids.picking_type_id.code',
    )
    def _compute_gn_import_split_available(self):
        for order in self:
            has_draft_incoming = any(
                p.state not in ('done', 'cancel')
                and p.picking_type_id.code == 'incoming'
                for p in order.picking_ids
            )
            order.gn_import_split_available = bool(
                order.gn_labhospy_compra_internacional
                and order.state in ('purchase', 'done')
                and has_draft_incoming
            )

    def action_gn_import_split_reception(self):
        self.ensure_one()
        if not self.gn_labhospy_compra_internacional:
            raise UserError(_(
                'La división planificada de recepciones solo aplica a '
                'órdenes marcadas como "Compra internacional".'
            ))
        pickings = self.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
            and p.picking_type_id.code == 'incoming'
        )
        if not pickings:
            raise UserError(_(
                'No hay recepciones en borrador para dividir en esta orden.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dividir recepción en dos'),
            'res_model': 'purchase.split.reception.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_id': self.id,
                'default_picking_id': pickings[:1].id,
            },
        }
