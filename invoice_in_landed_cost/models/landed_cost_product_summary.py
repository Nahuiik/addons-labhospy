# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.tools.float_utils import float_compare


class LandedCostProductSummary(models.TransientModel):
    _name = 'landed.cost.product.summary'
    _description = 'Landed Cost Product Summary'
    _order = 'product_name'

    landed_cost_id = fields.Many2one('stock.landed.cost', string='Landed Cost', required=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_name = fields.Char(string='Product', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True, digits=(16, 2))
    original_value = fields.Monetary(string='Original Value', readonly=True, currency_field='currency_id')
    total_landed_cost = fields.Monetary(string='Landed Cost', readonly=True, currency_field='currency_id')
    final_value = fields.Monetary(string='Final Value', readonly=True, currency_field='currency_id')
    unit_cost = fields.Monetary(string='Costo por Unidad', readonly=True, currency_field='currency_id', compute='_compute_unit_cost', store=False)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    margin_is_applied = fields.Boolean(
        string='Margen aplicado',
        compute='_compute_sale_margin_preview',
    )
    margin_price_drift = fields.Boolean(
        string='PVP distinto al aplicado',
        compute='_compute_sale_margin_preview',
        help='Indica si el PVP actual del producto ya no coincide con el aplicado en el costeo.',
    )
    list_price = fields.Float(
        string='PVP aplicado',
        compute='_compute_sale_margin_preview',
        digits='Product Price',
        help='PVP registrado al aplicar margen en este costeo, o PVP actual si aún no se aplicó.',
    )
    margin_on_cost_percent = fields.Float(
        string='% Margen aplicado',
        compute='_compute_sale_margin_preview',
        digits=(16, 2),
        help='Margen usado o referencial sobre el costo unitario del costeo.',
    )
    list_price_current = fields.Float(
        string='PVP (actual hoy)',
        compute='_compute_sale_margin_preview',
        digits='Product Price',
    )
    margin_current_percent = fields.Float(
        string='% Margen actual',
        compute='_compute_sale_margin_preview',
        digits=(16, 2),
    )

    @api.depends('final_value', 'quantity')
    def _compute_unit_cost(self):
        """Calcula el costo por unidad dividiendo el costo final entre la cantidad"""
        for record in self:
            if record.quantity and record.quantity > 0:
                record.unit_cost = record.final_value / record.quantity
            else:
                record.unit_cost = 0.0

    @api.depends(
        'product_id',
        'product_id.lst_price',
        'unit_cost',
        'landed_cost_id',
        'landed_cost_id.sale_margin_history_ids',
        'landed_cost_id.sale_margin_history_ids.line_ids',
        'landed_cost_id.sale_margin_history_ids.line_ids.price_applied',
        'landed_cost_id.sale_margin_history_ids.line_ids.margin_percent',
        'landed_cost_id.sale_margin_history_ids.line_ids.unit_cost',
    )
    def _compute_sale_margin_preview(self):
        """PVP/margen congelados al aplicar margen; columnas «actuales» solo si el PVP cambió."""
        HistoryLine = self.env['landed.cost.sale.margin.history.line']
        price_prec = self.env['decimal.precision'].precision_get('Product Price')

        lc_ids = self.mapped('landed_cost_id').ids
        product_ids = self.mapped('product_id').ids
        hist_map = {}
        if lc_ids and product_ids:
            for line in HistoryLine.search([
                ('history_id.landed_cost_id', 'in', lc_ids),
                ('product_id', 'in', product_ids),
            ]):
                key = (line.history_id.landed_cost_id.id, line.product_id.id)
                prev = hist_map.get(key)
                if not prev or line.history_id.applied_on > prev.history_id.applied_on or (
                    line.history_id.applied_on == prev.history_id.applied_on and line.id > prev.id
                ):
                    hist_map[key] = line

        for record in self:
            product = record.product_id
            unit_cost = record.unit_cost or 0.0
            key = (record.landed_cost_id.id, product.id) if product and record.landed_cost_id else None
            hist_line = hist_map.get(key, HistoryLine.browse()) if key else HistoryLine.browse()

            record.margin_is_applied = bool(hist_line)
            if hist_line:
                cost_base = hist_line.unit_cost or unit_cost
                record.list_price = hist_line.price_applied
                record.margin_on_cost_percent = hist_line.margin_percent
                record.list_price_current = product.lst_price if product else 0.0
                record.margin_price_drift = (
                    float_compare(
                        hist_line.price_applied,
                        record.list_price_current,
                        precision_digits=price_prec,
                    ) != 0
                )
                if record.margin_price_drift:
                    pvp_current = record.list_price_current or 0.0
                    record.margin_current_percent = (
                        (pvp_current - cost_base) / cost_base * 100.0 if cost_base > 0 else 0.0
                    )
                else:
                    record.margin_current_percent = hist_line.margin_percent
            elif product:
                record.list_price = product.lst_price
                pvp = record.list_price or 0.0
                record.margin_on_cost_percent = (
                    (pvp - unit_cost) / unit_cost * 100.0 if unit_cost > 0 else 0.0
                )
                record.list_price_current = record.list_price
                record.margin_current_percent = record.margin_on_cost_percent
                record.margin_price_drift = False
            else:
                record.list_price = 0.0
                record.margin_on_cost_percent = 0.0
                record.list_price_current = 0.0
                record.margin_current_percent = 0.0
                record.margin_price_drift = False

    @api.model
    def create_summary_lines(self, landed_cost):
        """Crea las líneas de resumen para un costo en destino"""
        self.search([('landed_cost_id', '=', landed_cost.id)]).unlink()
        
        products_summary = {}
        currency = landed_cost.company_id.currency_id
        
        # Primero, obtener las cantidades reales de los movimientos de stock de los pickings
        # Esto evita duplicar cantidades cuando hay múltiples líneas de ajuste para el mismo producto
        product_quantities = {}
        for picking in landed_cost.picking_ids:
            for move in picking.move_ids:
                if move.state == 'done' and move.product_id:
                    product_id = move.product_id.id
                    # Sumar la cantidad realmente recibida
                    # En Odoo 19, cuando el movimiento está 'done', podemos obtener la cantidad desde move_line_ids
                    if product_id not in product_quantities:
                        product_quantities[product_id] = 0.0
                    # Intentar obtener la cantidad desde move_line_ids primero
                    if move.move_line_ids:
                        # Sumar las cantidades de las líneas de movimiento (qty_done o quantity_done)
                        qty_done = 0.0
                        for move_line in move.move_line_ids:
                            # Intentar qty_done primero, luego quantity_done como fallback
                            qty_done += getattr(move_line, 'qty_done', 0.0) or getattr(move_line, 'quantity_done', 0.0) or 0.0
                        if qty_done > 0:
                            product_quantities[product_id] += qty_done
                        else:
                            # Si no hay qty_done, usar la cantidad del movimiento
                            product_quantities[product_id] += move.quantity
                    else:
                        # Si no hay move_line_ids, usar la cantidad del movimiento cuando está en estado done
                        product_quantities[product_id] += move.quantity
        
        # Agrupar costos por producto desde valuation_adjustment_lines.
        # En stock_landed_costs estándar, former_cost = move._get_value(): valor total del movimiento
        # (no por unidad). additional_landed_cost = fracción total asignada desde esa línea de costo.
        # Hay una fila de ajuste por (movimiento × línea de costo), repitiendo el mismo former_cost;
        # no multiplicar por quantity ni sumar final_cost*qty (inflaba como si hubiera conversión).
        seen_former_keys = set()

        for adj_line in landed_cost.valuation_adjustment_lines:
            product = adj_line.product_id
            if not product:
                continue

            product_key = product.id
            if product_key not in products_summary:
                qty = product_quantities.get(product_key, adj_line.quantity)
                products_summary[product_key] = {
                    'landed_cost_id': landed_cost.id,
                    'product_id': product.id,
                    'product_name': product.display_name,
                    'quantity': qty,
                    'original_value': 0.0,
                    'total_landed_cost': 0.0,
                    'final_value': 0.0,
                    'currency_id': currency.id,
                }

            if adj_line.move_id:
                fk = (product_key, adj_line.move_id.id)
            else:
                fk = (product_key, 'adj', adj_line.id)
            if fk not in seen_former_keys:
                products_summary[product_key]['original_value'] += adj_line.former_cost
                seen_former_keys.add(fk)

            products_summary[product_key]['total_landed_cost'] += adj_line.additional_landed_cost

        for product_key in products_summary:
            s = products_summary[product_key]
            s['final_value'] = s['original_value'] + s['total_landed_cost']

        # Crear los registros
        lines = []
        for product_key in sorted(products_summary.keys(), key=lambda k: products_summary[k]['product_name']):
            lines.append(products_summary[product_key])
        
        if lines:
            return self.create(lines)
        return self

