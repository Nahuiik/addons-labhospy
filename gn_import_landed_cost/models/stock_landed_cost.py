"""Reparto de costo en destino por picking (compras internacionales).

Extiende ``stock.landed.cost.lines`` con un ``expense_scope`` opcional que
permite atar la línea a un picking específico. Al calcular el costeo, cada
línea global sigue prorrateándose sobre todos los pickings, mientras que las
líneas ``picking`` solo reparten sobre los movimientos de su recepción.
"""
from collections import defaultdict

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    def _get_moves_for_cost_line(self, cost_line):
        """Movimientos elegibles para prorratear una línea de gasto.

        Global: todos los pickings del LC. Picking: solo el picking indicado
        (siempre acotado a los pickings del propio LC para evitar mezclas).
        """
        self.ensure_one()
        moves = self.picking_ids.move_ids
        if cost_line.expense_scope == 'picking' and cost_line.picking_id:
            if cost_line.picking_id not in self.picking_ids:
                return self.env['stock.move']
            moves = moves.filtered(
                lambda m: m.picking_id == cost_line.picking_id
            )
        return moves

    def _get_valuation_line_vals_for_move(self, move):
        """Construye el dict de línea de valoración para un ``stock.move``."""
        qty = move.product_uom._compute_quantity(move.quantity, move.product_id.uom_id)
        return {
            'product_id': move.product_id.id,
            'move_id': move.id,
            'quantity': qty,
            'former_cost': move._get_value(),
            'weight': move.product_id.weight * qty,
            'volume': move.product_id.volume * qty,
        }

    def compute_landed_cost(self):
        """Recalcula ajustes de valoración con reparto por scope de la línea.

        Sobrescribe la implementación base para calcular totales (qty, peso,
        volumen, coste) por línea de costo. Así las líneas ``picking`` no se
        diluyen con productos de otros pickings.
        """
        # Si ninguna línea usa scope 'picking', delegamos en super() para
        # mantener el comportamiento exacto de invoice_in_landed_cost.
        if all(l.expense_scope != 'picking' for c in self for l in c.cost_lines):
            return super().compute_landed_cost()

        AdjustementLines = self.env['stock.valuation.adjustment.lines']
        AdjustementLines.search([('cost_id', 'in', self.ids)]).unlink()

        towrite_dict = {}
        for cost in self.filtered(lambda c: c._get_targeted_move_ids()):
            cost = cost.with_company(cost.company_id)
            rounding = cost.currency_id.rounding

            # Cache de movimientos elegibles por línea + totales por línea.
            moves_by_line = {}
            totals_by_line = {}
            for cost_line in cost.cost_lines:
                moves = cost._get_moves_for_cost_line(cost_line)
                moves = moves.filtered(
                    lambda m: m.product_id.cost_method in ('fifo', 'average')
                    and m.state != 'cancel'
                    and m.quantity
                )
                moves_by_line[cost_line.id] = moves
                total_qty = total_cost = total_weight = total_volume = 0.0
                total_line = 0
                for move in moves:
                    qty = move.product_uom._compute_quantity(
                        move.quantity, move.product_id.uom_id
                    )
                    total_qty += qty
                    total_weight += move.product_id.weight * qty
                    total_volume += move.product_id.volume * qty
                    total_cost += cost.currency_id.round(move._get_value())
                    total_line += 1
                totals_by_line[cost_line.id] = {
                    'qty': total_qty,
                    'weight': total_weight,
                    'volume': total_volume,
                    'cost': total_cost,
                    'line_count': total_line,
                }

            # Crear una adjustment line por (cost_line, move elegible).
            adj_lines_by_line = defaultdict(list)
            for cost_line in cost.cost_lines:
                for move in moves_by_line[cost_line.id]:
                    vals = cost._get_valuation_line_vals_for_move(move)
                    vals.update({
                        'cost_id': cost.id,
                        'cost_line_id': cost_line.id,
                    })
                    adj = AdjustementLines.create(vals)
                    adj_lines_by_line[cost_line.id].append(adj)

            for line in cost.cost_lines:
                totals = totals_by_line[line.id]
                adjustments = adj_lines_by_line[line.id]
                if not adjustments:
                    continue
                value_split = 0.0
                last_adj_id = None
                for valuation in adjustments:
                    value = 0.0
                    if line.split_method == 'by_quantity' and totals['qty']:
                        per_unit = line.price_unit / totals['qty']
                        value = valuation.quantity * per_unit
                    elif line.split_method == 'by_weight' and totals['weight']:
                        per_unit = line.price_unit / totals['weight']
                        value = valuation.weight * per_unit
                    elif line.split_method == 'by_volume' and totals['volume']:
                        per_unit = line.price_unit / totals['volume']
                        value = valuation.volume * per_unit
                    elif line.split_method == 'equal' and totals['line_count']:
                        value = line.price_unit / totals['line_count']
                    elif line.split_method == 'by_current_cost_price' and totals['cost']:
                        per_unit = line.price_unit / totals['cost']
                        value = valuation.former_cost * per_unit
                    elif totals['line_count']:
                        value = line.price_unit / totals['line_count']

                    if rounding:
                        value = tools.float_round(
                            value, precision_rounding=rounding, rounding_method='HALF-UP'
                        )
                    value_split += value
                    towrite_dict[valuation.id] = towrite_dict.get(valuation.id, 0.0) + value
                    last_adj_id = valuation.id

                rounding_diff = cost.currency_id.round(line.price_unit - value_split)
                if not cost.currency_id.is_zero(rounding_diff) and last_adj_id is not None:
                    towrite_dict[last_adj_id] += rounding_diff

        for adj_id, value in towrite_dict.items():
            AdjustementLines.browse(adj_id).write({'additional_landed_cost': value})

        # Post-proceso heredado de invoice_in_landed_cost: PO en ajustes +
        # resumen por producto. Se ejecuta explícitamente porque no llamamos
        # a super() en este flujo.
        self._assign_purchase_order_to_adjustment_lines()
        for cost in self:
            if cost.id:
                self.env['landed.cost.product.summary'].create_summary_lines(cost)
        return True


class StockLandedCostLine(models.Model):
    _inherit = 'stock.landed.cost.lines'

    expense_scope = fields.Selection(
        [
            ('global', 'Toda la importación'),
            ('picking', 'Solo esta recepción'),
        ],
        string='Alcance del gasto',
        default='global',
        required=True,
        help='"Toda la importación" prorratea el gasto en todos los '
        'pickings del costeo. "Solo esta recepción" lo aplica '
        'únicamente a los productos del picking indicado.',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Recepción',
        index='btree_not_null',
        help='Recepción sobre la que se prorratea este gasto cuando el '
        'alcance es "Solo esta recepción".',
    )

    @api.constrains('expense_scope', 'picking_id', 'cost_id')
    def _check_picking_scope(self):
        for line in self:
            if line.expense_scope != 'picking':
                continue
            if not line.picking_id:
                raise ValidationError(_(
                    'La línea "%s" tiene alcance "Solo esta recepción" '
                    'pero no indica la recepción destino.'
                ) % (line.name or line.product_id.display_name or ''))
            if line.cost_id and line.picking_id not in line.cost_id.picking_ids:
                raise ValidationError(_(
                    'La recepción %s no está incluida en las transferencias '
                    'del costeo. Añádala primero al costo en destino.'
                ) % line.picking_id.name)

    @api.onchange('expense_scope')
    def _onchange_expense_scope(self):
        if self.expense_scope == 'global':
            self.picking_id = False
