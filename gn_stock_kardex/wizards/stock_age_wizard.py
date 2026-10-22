# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import date as date_type

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero, float_round


class GnStockAgeWizard(models.TransientModel):
    _name = 'gn.stock.age.wizard'
    _description = 'Asistente de Antigüedad de Stock'

    company_id = fields.Many2one(
        'res.company', string='Compañía',
        required=True, default=lambda self: self.env.company,
    )
    categ_ids = fields.Many2many(
        'product.category',
        'gn_stock_age_wizard_categ_rel',
        'wizard_id', 'categ_id',
        string='Categorías de producto',
        help='Vacío = todas las categorías.',
    )
    product_ids = fields.Many2many(
        'product.product',
        'gn_stock_age_wizard_product_rel',
        'wizard_id', 'product_id',
        string='Productos',
        domain="[('is_storable', '=', True)]",
        help='Vacío = todos los productos con stock.',
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Almacén',
        domain="[('company_id', '=', company_id)]",
    )
    breakdown_days = fields.Integer(
        string='Días por rango', default=60, required=True,
        help='Tamaño de cada rango de antigüedad en días.',
    )
    num_brackets = fields.Integer(
        string='Número de rangos', default=6, required=True,
        help='Cantidad de rangos a mostrar (más uno "Older").',
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.warehouse_id and self.warehouse_id.company_id != self.company_id:
            self.warehouse_id = False

    # ── Bracket helpers ──

    def _get_brackets(self):
        """Return list of bracket tuples: [(label, day_from, day_to), ...]"""
        d = self.breakdown_days
        n = self.num_brackets
        brackets = []
        for i in range(n):
            day_from = i * d + 1
            day_to = (i + 1) * d
            brackets.append((f'{day_from} - {day_to}', day_from, day_to))
        last_day = n * d + 1
        brackets.append((f'> {last_day - 1}', last_day, 999999))
        return brackets

    # ── Core calculation ──

    def _compute_age_data(self):
        """Returns list of dicts with age breakdown per product."""
        self.ensure_one()
        today = fields.Date.today()
        company_id = self.company_id.id
        brackets = self._get_brackets()

        # Resolve internal locations
        loc_domain = [('usage', '=', 'internal'), ('company_id', '=', company_id)]
        if self.warehouse_id:
            loc_domain.append(('warehouse_id', '=', self.warehouse_id.id))
        internal_loc_ids = self.env['stock.location'].search(loc_domain).ids
        if not internal_loc_ids:
            raise UserError(_('No se encontraron ubicaciones internas.'))

        # Get current stock from quants joined with product for cost
        cid_str = str(company_id)
        self.env.cr.execute("""
            SELECT sq.product_id, SUM(sq.quantity) AS qty,
                   SUM(sq.quantity *
                       COALESCE((pp.standard_price->>%s)::numeric, 0)) AS total_value
              FROM stock_quant sq
              JOIN product_product pp ON pp.id = sq.product_id
             WHERE sq.company_id = %s
               AND sq.location_id = ANY(%s)
               AND sq.quantity > 0
             GROUP BY sq.product_id
            HAVING SUM(sq.quantity) > 0
        """, (cid_str, company_id, internal_loc_ids))
        quant_data = {r['product_id']: r for r in self.env.cr.dictfetchall()}

        if not quant_data:
            return [], brackets

        # Filter by product/category
        product_ids = list(quant_data.keys())
        if self.product_ids:
            product_ids = [pid for pid in product_ids if pid in self.product_ids.ids]
        if self.categ_ids:
            self.env.cr.execute("""
                SELECT pp.id
                  FROM product_product pp
                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                 WHERE pp.id = ANY(%s) AND pt.categ_id = ANY(%s)
            """, (product_ids, list(self.categ_ids.ids)))
            product_ids = [r[0] for r in self.env.cr.fetchall()]

        if not product_ids:
            return [], brackets

        # Get incoming done moves sorted oldest first
        self.env.cr.execute("""
            SELECT sm.product_id, sm.date::date AS move_date,
                   sm.quantity AS qty,
                   ABS(COALESCE(sm.price_unit, 0)) AS unit_cost
              FROM stock_move sm
             WHERE sm.state = 'done'
               AND sm.company_id = %s
               AND sm.product_id = ANY(%s)
               AND sm.location_dest_id = ANY(%s)
               AND sm.location_id NOT IN (
                   SELECT id FROM stock_location WHERE usage = 'internal' AND company_id = %s
               )
             ORDER BY sm.product_id, sm.date ASC
        """, (company_id, product_ids, internal_loc_ids, company_id))
        moves_raw = self.env.cr.dictfetchall()

        moves_by_product = defaultdict(list)
        for m in moves_raw:
            moves_by_product[m['product_id']].append(m)

        # Prefetch product info
        products = self.env['product.product'].browse(product_ids)
        product_map = {p.id: p for p in products}

        rows = []
        for pid in sorted(product_ids, key=lambda x: product_map.get(x, self.env['product.product']).display_name):
            product = product_map.get(pid)
            if not product:
                continue
            q = quant_data.get(pid)
            if not q:
                continue

            remaining = q['qty']
            total_stock = float_round(remaining, precision_digits=2)
            stock_value = float_round(q['total_value'], precision_digits=2)
            unit_cost = float_round(stock_value / total_stock, precision_digits=2) if total_stock else 0.0

            age_buckets = [{'stock': 0.0, 'value': 0.0} for _ in brackets]
            incoming = moves_by_product.get(pid, [])

            for mv in incoming:
                if float_is_zero(remaining, precision_digits=4):
                    break
                move_qty = mv['qty'] or 0.0
                mv_unit_cost = mv['unit_cost'] or unit_cost
                assign = min(move_qty, remaining)
                if float_is_zero(assign, precision_digits=4):
                    continue

                age_days = (today - mv['move_date']).days if mv['move_date'] else 0
                for idx, (label, d_from, d_to) in enumerate(brackets):
                    if d_from <= age_days <= d_to:
                        age_buckets[idx]['stock'] += assign
                        age_buckets[idx]['value'] += assign * mv_unit_cost
                        break

                remaining -= assign

            # Any remaining stock goes to oldest bracket
            if remaining > 0.01:
                age_buckets[-1]['stock'] += remaining
                age_buckets[-1]['value'] += remaining * unit_cost

            # Round buckets
            for b in age_buckets:
                b['stock'] = float_round(b['stock'], precision_digits=2)
                b['value'] = float_round(b['value'], precision_digits=2)

            rows.append({
                'product_id': pid,
                'product_name': product.display_name,
                'default_code': product.default_code or '',
                'categ_name': product.categ_id.complete_name if product.categ_id else '',
                'total_stock': total_stock,
                'stock_value': stock_value,
                'unit_cost': unit_cost,
                'buckets': age_buckets,
            })

        return rows, brackets

    # ── Actions ──

    def action_view_onscreen(self):
        self.ensure_one()
        rows, brackets = self._compute_age_data()
        bracket_labels = [b[0] for b in brackets]
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_stock_age_preview',
            'name': _('Antigüedad de Stock'),
            'target': 'current',
            'context': {
                'age_rows': rows,
                'age_brackets': bracket_labels,
                'age_company_name': self.company_id.name,
                'age_warehouse_name': self.warehouse_id.name if self.warehouse_id else '',
                'age_breakdown_days': self.breakdown_days,
            },
        }

    def action_print_xlsx(self):
        self.ensure_one()
        return self.env.ref('gn_stock_kardex.action_report_stock_age_xlsx').report_action(self)

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('gn_stock_kardex.action_report_stock_age_pdf').report_action(self)
