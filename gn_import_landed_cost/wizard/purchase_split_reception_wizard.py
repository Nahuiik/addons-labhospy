"""Wizard para dividir una recepción en dos pickings.

Se dispara desde una orden de compra internacional cuyo picking de entrada
sigue en borrador. Permite indicar, por cada línea, qué cantidad va a la
recepción 1 (el picking original) y qué cantidad al nuevo picking 2. Al
confirmar, ajusta el picking original y crea un segundo picking con los
movimientos restantes.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class PurchaseSplitReceptionWizard(models.TransientModel):
    _name = 'purchase.split.reception.wizard'
    _description = 'Dividir recepción en dos pickings'

    purchase_id = fields.Many2one(
        'purchase.order', required=True, readonly=True,
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Recepción original',
        required=True,
        readonly=True,
        domain="[('id', 'in', available_picking_ids)]",
    )
    available_picking_ids = fields.Many2many(
        'stock.picking',
        compute='_compute_available_picking_ids',
    )
    line_ids = fields.One2many(
        'purchase.split.reception.wizard.line',
        'wizard_id',
        string='Líneas',
    )

    @api.depends('purchase_id')
    def _compute_available_picking_ids(self):
        for wiz in self:
            wiz.available_picking_ids = wiz.purchase_id.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel')
                and p.picking_type_id.code == 'incoming'
            )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        picking_id = vals.get('picking_id') or self.env.context.get('default_picking_id')
        if picking_id and 'line_ids' in fields_list:
            picking = self.env['stock.picking'].browse(picking_id)
            lines = []
            for move in picking.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and m.product_uom_qty
            ):
                lines.append((0, 0, {
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'total_qty': move.product_uom_qty,
                    'qty_first': move.product_uom_qty,
                    'qty_second': 0.0,
                }))
            vals['line_ids'] = lines
        return vals

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay líneas para dividir.'))

        picking1 = self.picking_id
        moves_to_move = self.env['stock.move']
        move_split_specs = []

        for line in self.line_ids:
            move = line.move_id
            precision = move.product_uom.rounding
            qty_first = line.qty_first
            qty_second = line.qty_second
            if float_compare(qty_first + qty_second, line.total_qty,
                             precision_rounding=precision) != 0:
                raise ValidationError(_(
                    'La suma de cantidades (Recepción 1 + Recepción 2) '
                    'debe ser igual a la cantidad original en cada línea: %s'
                ) % move.product_id.display_name)
            if float_compare(qty_first, 0.0, precision_rounding=precision) < 0 or \
               float_compare(qty_second, 0.0, precision_rounding=precision) < 0:
                raise ValidationError(_(
                    'Las cantidades no pueden ser negativas.'
                ))

            if float_is_zero(qty_second, precision_rounding=precision):
                continue
            if float_is_zero(qty_first, precision_rounding=precision):
                moves_to_move |= move
                continue
            move_split_specs.append((move, qty_second))

        if not move_split_specs and not moves_to_move:
            raise UserError(_(
                'No indicó ninguna cantidad para la Recepción 2. Ajuste '
                'las cantidades o cancele la división.'
            ))

        picking2 = picking1.copy({
            'name': '/',
            'move_ids': [],
            'move_line_ids': [],
            'backorder_id': False,
            'gn_import_reception_split': True,
            'gn_import_reception_part': 'second',
        })

        for move in moves_to_move:
            move.write({'picking_id': picking2.id, 'picked': False})

        StockMove = self.env['stock.move']
        for move, qty in move_split_specs:
            new_vals = move._split(qty)
            for vals in new_vals:
                vals['picking_id'] = picking2.id
                new_move = StockMove.create(vals)
                new_move._action_confirm(merge=False)

        picking1.write({
            'gn_import_reception_split': True,
            'gn_import_reception_part': 'first',
        })
        picking2.action_confirm()
        picking2.action_assign()

        picking1.message_post(body=_(
            'Recepción dividida: se creó %s con los productos de la '
            'Recepción 2.'
        ) % picking2._get_html_link())
        picking2.message_post(body=_(
            'Este picking se generó al dividir la recepción original %s.'
        ) % picking1._get_html_link())

        return {
            'type': 'ir.actions.act_window',
            'name': _('Recepciones'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', (picking1 | picking2).ids)],
        }


class PurchaseSplitReceptionWizardLine(models.TransientModel):
    _name = 'purchase.split.reception.wizard.line'
    _description = 'Línea del wizard de división de recepción'

    wizard_id = fields.Many2one(
        'purchase.split.reception.wizard', required=True, ondelete='cascade',
    )
    move_id = fields.Many2one(
        'stock.move', required=True, readonly=True,
    )
    product_id = fields.Many2one(
        'product.product', string='Producto', readonly=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom', string='UdM', readonly=True,
    )
    total_qty = fields.Float(
        string='Cantidad original', readonly=True,
        digits='Product Unit',
    )
    qty_first = fields.Float(
        string='Recepción 1', digits='Product Unit',
    )
    qty_second = fields.Float(
        string='Recepción 2', digits='Product Unit',
    )
    qty_balance = fields.Float(
        string='Diferencia',
        compute='_compute_qty_balance',
        digits='Product Unit',
        help='Debe quedar en cero antes de confirmar.',
    )

    @api.depends('qty_first', 'qty_second', 'total_qty')
    def _compute_qty_balance(self):
        for line in self:
            line.qty_balance = line.total_qty - (line.qty_first + line.qty_second)

    @api.onchange('qty_first')
    def _onchange_qty_first(self):
        for line in self:
            precision = line.product_uom_id.rounding or 0.01
            if line.qty_first is False:
                continue
            new_second = line.total_qty - line.qty_first
            if float_compare(new_second, 0.0, precision_rounding=precision) < 0:
                new_second = 0.0
            line.qty_second = new_second

    @api.onchange('qty_second')
    def _onchange_qty_second(self):
        for line in self:
            precision = line.product_uom_id.rounding or 0.01
            if line.qty_second is False:
                continue
            new_first = line.total_qty - line.qty_second
            if float_compare(new_first, 0.0, precision_rounding=precision) < 0:
                new_first = 0.0
            line.qty_first = new_first
