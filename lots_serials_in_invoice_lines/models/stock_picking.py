from odoo import models, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        # Antes de validar, aseguramos que las move lines tengan los lotes elegidos en la SO
        for picking in self:
            if picking.picking_type_id.code != 'outgoing':
                continue
            sale = picking.sale_id
            if not sale:
                continue
            # Construir mapa product_id -> lotes seleccionados por líneas de venta
            product_to_lots = {}
            for so_line in sale.order_line:
                if so_line.product_id and so_line.lot_ids:
                    product_to_lots.setdefault(so_line.product_id.id, [])
                    product_to_lots[so_line.product_id.id] += so_line.lot_ids.ids

            if not product_to_lots:
                continue

            for move in picking.move_ids:
                product_id = move.product_id.id
                if product_id not in product_to_lots:
                    continue
                selected_lot_ids = product_to_lots[product_id]
                # Limpiar move lines existentes si no respetan la selección
                move.move_line_ids.unlink()

                # Determinar cantidades por lote: 1 unidad por lote si tracking by serial; si tracked by lot, asignar toda qty al primer lote o repartir
                qty_to_assign = move.product_uom_qty
                if not qty_to_assign:
                    continue

                Product = move.product_id
                Uom = Product.uom_id

                Quant = self.env['stock.quant']
                location = move.location_id
                lots_created = 0.0

                def _available_qty(lot_id):
                    quants = Quant.search([
                        ('product_id', '=', Product.id),
                        ('location_id', 'child_of', location.id),
                        ('lot_id', '=', lot_id),
                    ])
                    return sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))

                if Product.tracking == 'serial':
                    # Cada serie representa 1 unidad
                    for lot_id in selected_lot_ids:
                        if qty_to_assign <= 0:
                            break
                        if _available_qty(lot_id) <= 0:
                            continue
                        self.env['stock.move.line'].create({
                            'move_id': move.id,
                            'picking_id': picking.id,
                            'product_id': Product.id,
                            'product_uom_id': Uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'qty_done': 1.0,
                            'lot_id': lot_id,
                        })
                        qty_to_assign -= 1.0
                        lots_created += 1.0
                    if qty_to_assign > 0:
                        raise UserError(_(f'No hay disponibilidad suficiente por número de serie para {Product.display_name}. Faltan {qty_to_assign} unidad(es).'))
                elif Product.tracking == 'lot':
                    # Asignar en orden hasta cubrir cantidad
                    for lot_id in selected_lot_ids:
                        if qty_to_assign <= 0:
                            break
                        avail = _available_qty(lot_id)
                        if avail <= 0:
                            continue
                        qty = min(qty_to_assign, avail)
                        self.env['stock.move.line'].create({
                            'move_id': move.id,
                            'picking_id': picking.id,
                            'product_id': Product.id,
                            'product_uom_id': Uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'qty_done': qty,
                            'lot_id': lot_id,
                        })
                        qty_to_assign -= qty
                        lots_created += qty
                    if qty_to_assign > 0:
                        raise UserError(_(f'No hay disponibilidad suficiente por lote para {Product.display_name}. Faltan {qty_to_assign} {Uom.name}.'))
                else:
                    # Producto no trazable: no forzamos nada
                    continue

        return super().button_validate()


