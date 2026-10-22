# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time as time_type

import pytz

from odoo import _, api, fields, models
from odoo.tools.float_utils import float_is_zero, float_round
from odoo.tools.misc import format_datetime


class GnStockKardexReport(models.AbstractModel):
    _name = 'report.gn_stock_kardex.report_kardex_template'
    _description = 'Kardex AVCO PDF'

    @api.model
    def _apply_avco_step(self, qty, value, res_model, total_value, total_quantity, avco):
        added_value = 0.0
        if res_model == 'stock.move':
            if qty > 0:
                added_value = value
            elif qty < 0:
                added_value = avco * qty
            total_value += added_value
            total_quantity += qty
        elif res_model == 'product.value':
            added_value = (value * total_quantity) - total_value
            total_value = value * total_quantity

        if not float_is_zero(total_quantity, precision_digits=6):
            avco = total_value / total_quantity
        else:
            avco = 0.0
        return total_value, total_quantity, avco, added_value

    # ── Timezone helpers ──

    @api.model
    def _dt_to_user_tz(self, dt_value):
        if not dt_value:
            return None
        tzname = self.env.user.tz or 'UTC'
        tz = pytz.timezone(tzname)
        if isinstance(dt_value, str):
            dt_value = fields.Datetime.from_string(dt_value)
        utc = pytz.UTC.localize(dt_value)
        return utc.astimezone(tz)

    @api.model
    def _format_dt_table(self, dt_value):
        local = self._dt_to_user_tz(dt_value)
        if not local:
            return ''
        return local.strftime('%Y-%m-%d %H:%M:%S')

    @api.model
    def _format_dt_header(self, dt_value):
        if not dt_value:
            return ''
        return format_datetime(
            self.env, dt_value,
            tz=self.env.user.tz or 'UTC',
            dt_format='medium',
        )

    @api.model
    def _user_tz_start_utc(self, day):
        tzname = self.env.user.tz or 'UTC'
        tz = pytz.timezone(tzname)
        local = tz.localize(datetime.combine(day, time_type.min))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    @api.model
    def _user_tz_end_utc(self, day):
        tzname = self.env.user.tz or 'UTC'
        tz = pytz.timezone(tzname)
        local = tz.localize(datetime.combine(day, time_type(23, 59, 59)))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    # ── Bulk data fetch via SQL ──

    @api.model
    def _fetch_avco_rows(self, company_id, product_ids, date_to,
                         branch_id=False, warehouse_id=False, location_id=False,
                         location_ids=None):
        """Fetch all stock.avco.report rows up to date_to via raw SQL (fast)."""
        loc_ids = []
        if location_ids:
            loc_ids = [int(x) for x in location_ids if x]
        elif location_id:
            loc_ids = [int(location_id)]
        need_join = branch_id or warehouse_id or bool(loc_ids)
        if need_join:
            extra = ""
            params_extra = []
            if branch_id:
                extra += " AND (r.res_model_name != 'stock.move' OR sm.branch_id = %s)"
                params_extra.append(branch_id)
            if warehouse_id:
                extra += " AND (r.res_model_name != 'stock.move' OR sm.warehouse_id = %s)"
                params_extra.append(warehouse_id)
            if loc_ids:
                extra += (
                    " AND (r.res_model_name != 'stock.move' OR "
                    "sm.location_id = ANY(%s) OR sm.location_dest_id = ANY(%s))"
                )
                params_extra.extend([loc_ids, loc_ids])
            self.env.cr.execute(f"""
                SELECT r.id, r.product_id, r.date, r.quantity, r.value,
                       r.res_model_name, r.reference, r.description
                  FROM stock_avco_report r
                  LEFT JOIN stock_move sm ON sm.id = r.id AND r.res_model_name = 'stock.move'
                 WHERE r.company_id = %s
                   AND r.product_id = ANY(%s)
                   AND r.date <= %s
                   {extra}
                 ORDER BY r.product_id, r.date, r.id
            """, (company_id, list(product_ids), date_to, *params_extra))
        else:
            self.env.cr.execute("""
                SELECT id, product_id, date, quantity, value,
                       res_model_name, reference, description
                  FROM stock_avco_report
                 WHERE company_id = %s
                   AND product_id = ANY(%s)
                   AND date <= %s
                 ORDER BY product_id, date, id
            """, (company_id, list(product_ids), date_to))
        return self.env.cr.dictfetchall()

    @api.model
    def _prefetch_moves(self, move_ids):
        """Bulk-fetch stock.move data needed for display/traceability."""
        if not move_ids:
            return {}
        self.env.cr.execute("""
            SELECT sm.id,
                   sm.date,
                   sm.origin,
                   sm.partner_id,
                   sp.id AS picking_id,
                   sp.name AS picking_name,
                   sp.origin AS picking_origin,
                   sp.partner_id AS picking_partner_id,
                   COALESCE(rpp.name, rpc.name, '') AS partner_name
              FROM stock_move sm
              LEFT JOIN stock_picking sp ON sp.id = sm.picking_id
              LEFT JOIN res_partner rpp ON rpp.id = sp.partner_id
              LEFT JOIN res_partner rpc ON rpc.id = sm.partner_id
             WHERE sm.id = ANY(%s)
        """, (list(move_ids),))
        return {r['id']: r for r in self.env.cr.dictfetchall()}

    @api.model
    def _prefetch_product_values(self, pv_ids):
        """Bulk-fetch product.value data."""
        if not pv_ids:
            return {}
        self.env.cr.execute("""
            SELECT id, date, description
              FROM product_value
             WHERE id = ANY(%s)
        """, (list(pv_ids),))
        return {r['id']: r for r in self.env.cr.dictfetchall()}

    # ── PDF report data ──

    @api.model
    def _get_kardex_data(self, company, products, date_from, date_to):
        if not products:
            return {
                'sections': [], 'company': company,
                'date_from': date_from, 'date_to': date_to,
            }

        rows = self._fetch_avco_rows(company.id, products.ids, date_to)
        by_product = defaultdict(list)
        for row in rows:
            by_product[row['product_id']].append(row)

        sections = []
        for product in products.sorted(lambda p: p.display_name):
            recs = by_product.get(product.id, [])
            if not recs:
                continue

            before = [r for r in recs if (r['date'].date() if hasattr(r['date'], 'date') else r['date']) < date_from]
            during = [r for r in recs if (r['date'].date() if hasattr(r['date'], 'date') else r['date']) >= date_from]

            tv = tq = avco = 0.0
            for r in before:
                tv, tq, avco, _a = self._apply_avco_step(
                    r['quantity'], r['value'], r['res_model_name'], tv, tq, avco)

            lines = [{
                'es_inicio': True,
                'date': date_from,
                'reference': _('Saldo inicial'),
                'description': '',
                'qty_in': 0.0, 'qty_out': 0.0, 'value_move': 0.0,
                'balance_qty': tq, 'balance_value': tv, 'unit_cost': avco,
            }]

            for r in during:
                tv, tq, avco, added = self._apply_avco_step(
                    r['quantity'], r['value'], r['res_model_name'], tv, tq, avco)
                qty = r['quantity']
                lines.append({
                    'es_inicio': False,
                    'date': r['date'],
                    'reference': r['reference'] or '',
                    'description': (r['description'] or '')[:200],
                    'qty_in': qty if qty > 0 else 0.0,
                    'qty_out': -qty if qty < 0 else 0.0,
                    'value_move': added,
                    'balance_qty': tq, 'balance_value': tv, 'unit_cost': avco,
                    'tipo': r['res_model_name'],
                })

            sections.append({
                'product': product, 'uom': product.uom_id.name, 'lines': lines,
            })

        return {
            'company': company, 'date_from': date_from,
            'date_to': date_to, 'sections': sections,
        }

    # ── OWL JSON payload (optimized) ──

    @api.model
    def get_kardex_json(self, company_id, product_ids, date_from, date_to,
                        branch_id=False, warehouse_id=False, location_id=False,
                        location_ids=None):
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        company = self.env['res.company'].browse(company_id)
        if not company.exists():
            return {'error': _('Compañía no válida.'), 'sections': []}

        products = self.env['product.product'].browse(product_ids or []).exists()
        if not products:
            return {
                'company_name': company.name,
                'currency_symbol': company.currency_id.symbol,
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'date_from_display': '', 'date_to_display': '',
                'sections': [],
            }

        currency = company.currency_id
        prec = currency.decimal_places

        dt_from_utc = self._user_tz_start_utc(date_from)
        dt_to_utc = self._user_tz_end_utc(date_to)
        date_from_display = self._format_dt_header(dt_from_utc)
        date_to_display = self._format_dt_header(dt_to_utc)

        rows = self._fetch_avco_rows(company_id, products.ids, date_to,
                                     branch_id=branch_id, warehouse_id=warehouse_id,
                                     location_id=location_id, location_ids=location_ids)

        by_product = defaultdict(list)
        move_ids_needed = set()
        pv_ids_needed = set()
        for row in rows:
            by_product[row['product_id']].append(row)
            rd = row['date'].date() if hasattr(row['date'], 'date') else row['date']
            if rd >= date_from:
                if row['res_model_name'] == 'stock.move':
                    move_ids_needed.add(row['id'])
                elif row['res_model_name'] == 'product.value':
                    pv_ids_needed.add(-row['id'])

        moves_map = self._prefetch_moves(move_ids_needed)
        pvs_map = self._prefetch_product_values(pv_ids_needed)

        opening_display = self._format_dt_table(dt_from_utc)

        product_map = {p.id: p for p in products}
        sorted_pids = sorted(product_map.keys(), key=lambda pid: product_map[pid].display_name)

        sections_out = []
        for pid in sorted_pids:
            recs = by_product.get(pid)
            if not recs:
                continue

            product = product_map[pid]
            before = []
            during = []
            for r in recs:
                rd = r['date'].date() if hasattr(r['date'], 'date') else r['date']
                if rd < date_from:
                    before.append(r)
                else:
                    during.append(r)

            tv = tq = avco = 0.0
            for r in before:
                tv, tq, avco, _a = self._apply_avco_step(
                    r['quantity'], r['value'], r['res_model_name'], tv, tq, avco)

            prev_balance = {
                'qty': float_round(tq, precision_digits=4),
                'unit_cost': float_round(avco, precision_digits=prec + 4),
                'total_value': float_round(tv, precision_digits=prec),
            }

            lines_json = [{
                'row_type': 'opening',
                'datetime_display': opening_display,
                'reference': 'Saldo anterior',
                'ref_action': False,
                'origin': '', 'partner_name': '',
                'in_qty': 0.0, 'in_unit_cost': 0.0, 'in_total': 0.0,
                'out_qty': 0.0, 'out_unit_cost': 0.0, 'out_total': 0.0,
                'bal_qty': float_round(tq, precision_digits=4),
                'bal_unit_cost': float_round(avco, precision_digits=prec + 4),
                'bal_total': float_round(tv, precision_digits=prec),
            }]

            sum_in_qty = sum_out_qty = 0.0

            for r in during:
                avco_before = avco
                qty = r['quantity']
                value = r['value']
                res_model = r['res_model_name']

                tv, tq, avco, added = self._apply_avco_step(
                    qty, value, res_model, tv, tq, avco)

                ref_action = False
                reference = r['reference'] or ''
                origin = ''
                partner_name = ''
                dt_display = ''

                if res_model == 'stock.move':
                    mv = moves_map.get(r['id'])
                    if mv:
                        dt_display = self._format_dt_table(mv['date'])
                        partner_name = mv['partner_name'] or ''
                        if mv['picking_id']:
                            origin = mv['picking_origin'] or mv['origin'] or ''
                            reference = mv['picking_name'] or reference
                            ref_action = {'res_model': 'stock.picking', 'res_id': mv['picking_id']}
                        else:
                            origin = mv['origin'] or ''
                            ref_action = {'res_model': 'stock.move', 'res_id': mv['id']}
                elif res_model == 'product.value':
                    pv = pvs_map.get(-r['id'])
                    if pv:
                        dt_display = self._format_dt_table(pv['date'])
                        origin = (pv['description'] or '')[:200]
                        ref_action = {'res_model': 'product.value', 'res_id': -r['id']}

                if not dt_display:
                    raw_dt = r['date']
                    if not isinstance(raw_dt, datetime):
                        raw_dt = datetime.combine(raw_dt, time_type.min)
                    dt_display = self._format_dt_table(raw_dt)

                in_qty = in_uc = in_tot = 0.0
                out_qty = out_uc = out_tot = 0.0

                if not float_is_zero(qty, precision_digits=6):
                    if qty > 0:
                        in_qty = qty
                        in_tot = value if res_model == 'stock.move' else added
                        in_uc = float_round(in_tot / qty, precision_digits=prec + 4) if qty else 0.0
                        sum_in_qty += qty
                    else:
                        out_qty = qty
                        out_uc = float_round(avco_before, precision_digits=prec + 4)
                        out_tot = float_round(added, precision_digits=prec)
                        sum_out_qty += qty

                lines_json.append({
                    'row_type': 'move',
                    'datetime_display': dt_display,
                    'reference': reference,
                    'ref_action': ref_action,
                    'origin': (r['description'] or origin or '')[:500],
                    'partner_name': partner_name,
                    'in_qty': in_qty,
                    'in_unit_cost': in_uc,
                    'in_total': float_round(in_tot, precision_digits=prec),
                    'out_qty': out_qty,
                    'out_unit_cost': out_uc,
                    'out_total': float_round(out_tot, precision_digits=prec),
                    'bal_qty': float_round(tq, precision_digits=4),
                    'bal_unit_cost': float_round(avco, precision_digits=prec + 4),
                    'bal_total': float_round(tv, precision_digits=prec),
                })

            last = lines_json[-1] if lines_json else None
            totals = {
                'in_qty': float_round(sum_in_qty, precision_digits=4),
                'out_qty': float_round(sum_out_qty, precision_digits=4),
                'final_qty': last['bal_qty'] if last else 0.0,
                'final_unit_cost': last['bal_unit_cost'] if last else 0.0,
                'final_total': last['bal_total'] if last else 0.0,
            }

            categ_name = product.categ_id.complete_name if product.categ_id else ''

            sections_out.append({
                'product_id': product.id,
                'product_name': product.display_name,
                'default_code': product.default_code or '',
                'categ_name': categ_name,
                'uom': product.uom_id.name,
                'prev_balance': prev_balance,
                'lines': lines_json,
                'totals': totals,
            })

        branch_name = ''
        if branch_id:
            branch = self.env['res.branch'].browse(branch_id)
            if branch.exists():
                branch_name = branch.name
        warehouse_name = ''
        if warehouse_id:
            wh = self.env['stock.warehouse'].browse(warehouse_id)
            if wh.exists():
                warehouse_name = wh.name
        location_name = ''
        loc_ids_display = []
        if location_ids:
            loc_ids_display = [int(x) for x in location_ids if x]
        elif location_id:
            loc_ids_display = [int(location_id)]
        if loc_ids_display:
            locs = self.env['stock.location'].browse(loc_ids_display).exists()
            names = locs.mapped('complete_name')
            location_name = ', '.join(names) if len(names) <= 3 else f'{len(names)} ubicaciones'

        return {
            'company_name': company.name,
            'branch_name': branch_name,
            'warehouse_name': warehouse_name,
            'location_name': location_name,
            'currency_symbol': currency.symbol,
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
            'date_from_display': date_from_display,
            'date_to_display': date_to_display,
            'sections': sections_out,
        }

    # ── Summary data (grouped by category) ──

    @api.model
    def _get_summary_data(self, company, products, date_from, date_to,
                          branch_id=False, warehouse_id=False, location_id=False,
                          location_ids=None):
        if not products:
            return {
                'company': company, 'date_from': date_from, 'date_to': date_to,
                'categories': [], 'flat_rows': [],
            }

        rows = self._fetch_avco_rows(company.id, products.ids, date_to,
                                     branch_id=branch_id, warehouse_id=warehouse_id,
                                     location_id=location_id, location_ids=location_ids)
        by_product = defaultdict(list)
        for row in rows:
            by_product[row['product_id']].append(row)

        product_map = {p.id: p for p in products}
        prec = company.currency_id.decimal_places

        flat_rows = []
        for pid in sorted(product_map, key=lambda x: product_map[x].display_name):
            recs = by_product.get(pid)
            if not recs:
                continue
            product = product_map[pid]

            before = [r for r in recs if (r['date'].date() if hasattr(r['date'], 'date') else r['date']) < date_from]
            during = [r for r in recs if (r['date'].date() if hasattr(r['date'], 'date') else r['date']) >= date_from]

            if not during:
                continue

            tv = tq = avco = 0.0
            for r in before:
                tv, tq, avco, _a = self._apply_avco_step(
                    r['quantity'], r['value'], r['res_model_name'], tv, tq, avco)
            opening_qty = float_round(tq, precision_digits=4)

            sum_in = sum_out = 0.0
            for r in during:
                tv, tq, avco, _a = self._apply_avco_step(
                    r['quantity'], r['value'], r['res_model_name'], tv, tq, avco)
                qty = r['quantity']
                if r['res_model_name'] == 'stock.move':
                    if qty > 0:
                        sum_in += qty
                    elif qty < 0:
                        sum_out += qty

            closing_qty = float_round(tq, precision_digits=4)
            closing_total = float_round(tv, precision_digits=prec)
            closing_uc = float_round(avco, precision_digits=prec + 4)

            flat_rows.append({
                'product': product,
                'categ_name': product.categ_id.complete_name if product.categ_id else _('Sin categoría'),
                'opening_qty': opening_qty,
                'incoming': float_round(sum_in, precision_digits=4),
                'outgoing': float_round(sum_out, precision_digits=4),
                'closing_qty': closing_qty,
                'closing_unit_cost': closing_uc,
                'closing_total': closing_total,
            })

        categories = defaultdict(lambda: {'rows': [], 'opening': 0, 'incoming': 0, 'outgoing': 0, 'closing_qty': 0, 'closing_total': 0})
        for r in flat_rows:
            cat = r['categ_name']
            categories[cat]['rows'].append(r)
            categories[cat]['opening'] += r['opening_qty']
            categories[cat]['incoming'] += r['incoming']
            categories[cat]['outgoing'] += r['outgoing']
            categories[cat]['closing_qty'] += r['closing_qty']
            categories[cat]['closing_total'] += r['closing_total']

        sorted_categs = []
        for cname in sorted(categories):
            c = categories[cname]
            sorted_categs.append({
                'name': cname,
                'rows': c['rows'],
                'opening': float_round(c['opening'], precision_digits=4),
                'incoming': float_round(c['incoming'], precision_digits=4),
                'outgoing': float_round(c['outgoing'], precision_digits=4),
                'closing_qty': float_round(c['closing_qty'], precision_digits=4),
                'closing_total': float_round(c['closing_total'], precision_digits=prec),
            })

        return {
            'company': company, 'date_from': date_from, 'date_to': date_to,
            'categories': sorted_categs, 'flat_rows': flat_rows,
        }

    # ── PDF report values ──

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gn.stock.kardex.wizard'].browse(docids)
        w = wizard[0]
        values = self._get_kardex_data(w.company_id, w.product_ids, w.date_from, w.date_to)
        values['doc_ids'] = docids
        values['wizard'] = w
        return values


class GnStockKardexSummaryReport(models.AbstractModel):
    _name = 'report.gn_stock_kardex.report_kardex_summary_template'
    _description = 'Kardex Summary PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gn.stock.kardex.wizard'].browse(docids)
        w = wizard[0]
        report = self.env['report.gn_stock_kardex.report_kardex_template']
        products = w._resolve_products()
        branch_id = w.branch_id.id if w.branch_id else False
        warehouse_id = w.warehouse_id.id if w.warehouse_id else False
        location_id = w.location_id.id if w.location_id else False
        values = report._get_summary_data(
            w.company_id, products, w.date_from, w.date_to,
            branch_id=branch_id, warehouse_id=warehouse_id, location_id=location_id,
        )
        values['doc_ids'] = docids
        values['wizard'] = w
        return values
