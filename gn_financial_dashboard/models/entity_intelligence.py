# -*- coding: utf-8 -*-
"""Inteligencia de entidades (V20 Fase 3): productos, clientes y proveedores.

Estos motores reutilizan el dominio base del tablero y los filtros activos
(compañía, fechas, diarios, sucursal, analítica, proyecto). Calculan:

- **Top productos**: ranking por ingresos, costo, margen y unidades; análisis
  ABC (clasificación 80/15/5) y participación porcentual.
- **Inteligencia de clientes**: ranking de ingresos, frecuencia, DSO,
  exposición vencida y un score 0-100 que pondera valor, comportamiento de
  pago y antigüedad. Incluye recomendaciones automáticas.
- **Inteligencia de proveedores**: ranking de compras, dependencia
  (concentración), días promedio de pago (DPO), frecuencia y score 0-100.

No se almacenan resultados — todo se calcula por demanda con consultas
agregadas (read_group y SQL) para mantener el dashboard fluido.
"""
from collections import defaultdict
from datetime import date

from odoo import _, api, models
from odoo.exceptions import UserError


# Umbrales ABC en porcentaje acumulado de ingresos/compras.
ABC_A_THRESHOLD = 80.0  # primer 80%
ABC_B_THRESHOLD = 95.0  # siguiente 15%
# Score: ponderaciones (deben sumar 100).
CUSTOMER_SCORE_WEIGHTS = {
    'value': 30,      # peso por ingresos generados (vs. top cliente)
    'frequency': 15,  # peso por nº de facturas
    'payment': 30,    # peso por DSO (mejor = menor)
    'overdue': 20,    # peso por exposición vencida (mejor = menor)
    'tenure': 5,      # peso por antigüedad como cliente
}
SUPPLIER_SCORE_WEIGHTS = {
    'value': 25,
    'frequency': 15,
    'payment': 25,    # cumplimiento (DPO razonable, no en mora)
    'concentration': 25,  # mejor a menor dependencia (riesgo)
    'tenure': 10,
}
LIMIT_DEFAULT = 25


class GnFinancialDashboardEntities(models.AbstractModel):
    _inherit = 'gn.financial.dashboard'

    # ==================================================================
    # Top Productos (#8)
    # ==================================================================
    @api.model
    def get_product_intelligence(self, filters):
        """Devuelve top productos por ingresos/costo/margen + ABC."""
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        income_ids = [aid for aid, t in type_map.items() if t in ('income', 'income_other')]
        cogs_ids = [aid for aid, t in type_map.items() if t == 'expense_direct_cost']
        limit = int(filters.get('limit') or LIMIT_DEFAULT)

        # ------- Ingresos por producto -------
        rev_rows = self._product_sums(parsed, income_ids, sign=-1.0)
        # ------- Costo por producto -------
        cost_rows = self._product_sums(parsed, cogs_ids, sign=1.0)
        # ------- Unidades vendidas (signo del documento determina venta vs.
        # devolución; AML.quantity es positiva para facturas de venta y para
        # facturas de compra, así que filtramos por la cuenta para distinguir).
        qty_rows = self._product_quantities(parsed, income_ids)

        agg = defaultdict(lambda: {'revenue': 0.0, 'cost': 0.0, 'qty': 0.0,
                                    'frequency': 0, 'partners': set()})
        for pid, val, freq, partners in rev_rows:
            agg[pid]['revenue'] += val
            agg[pid]['frequency'] += freq
            agg[pid]['partners'].update(partners)
        for pid, val, _f, _p in cost_rows:
            agg[pid]['cost'] += val
        for pid, qty in qty_rows.items():
            agg[pid]['qty'] += qty

        items = []
        for pid, data in agg.items():
            if pid is None:
                continue
            revenue = data['revenue']
            cost = data['cost']
            margin = revenue - cost
            margin_pct = (margin / revenue * 100.0) if revenue else 0.0
            avg_price = (revenue / data['qty']) if data['qty'] else 0.0
            items.append({
                'product_id': pid,
                'revenue': round(revenue, 2),
                'cost': round(cost, 2),
                'margin': round(margin, 2),
                'margin_pct': round(margin_pct, 1),
                'qty': round(data['qty'], 2),
                'avg_price': round(avg_price, 2),
                'frequency': data['frequency'],
                'partners_count': len(data['partners']),
            })
        items.sort(key=lambda r: r['revenue'], reverse=True)
        total_revenue = sum(it['revenue'] for it in items)

        # Análisis ABC: orden por ingresos descendente, acumular %.
        cumulative = 0.0
        for it in items:
            it['pct'] = round((it['revenue'] / total_revenue * 100.0), 2) \
                if total_revenue else 0.0
            cumulative += it['pct']
            it['cum_pct'] = round(cumulative, 2)
            if cumulative <= ABC_A_THRESHOLD:
                it['abc'] = 'A'
            elif cumulative <= ABC_B_THRESHOLD:
                it['abc'] = 'B'
            else:
                it['abc'] = 'C'

        # Resolver nombres en lote (solo top + ABC=A).
        top_items = items[:limit]
        a_count = sum(1 for it in items if it['abc'] == 'A')
        b_count = sum(1 for it in items if it['abc'] == 'B')
        c_count = len(items) - a_count - b_count
        all_ids = [it['product_id'] for it in top_items]
        if all_ids:
            names = {p.id: p.display_name for p in
                     self.env['product.product'].sudo().browse(all_ids).exists()}
            for it in top_items:
                it['name'] = names.get(it['product_id'], _('(Producto eliminado)'))

        # Top negativos: productos donde margen < 0 (alerta).
        loss_items = [it for it in items if it['margin'] < -0.01]
        loss_items.sort(key=lambda r: r['margin'])
        loss_ids = [it['product_id'] for it in loss_items[:10]]
        if loss_ids:
            names2 = {p.id: p.display_name for p in
                      self.env['product.product'].sudo().browse(loss_ids).exists()}
            for it in loss_items[:10]:
                it['name'] = names2.get(it['product_id'], _('(Producto eliminado)'))

        return {
            'items': top_items,
            'loss_items': loss_items[:10],
            'total_revenue': round(total_revenue, 2),
            'total_products': len(items),
            'abc_summary': {
                'a_count': a_count, 'b_count': b_count, 'c_count': c_count,
                'a_revenue_pct': round(sum(it['pct'] for it in items if it['abc'] == 'A'), 1),
                'b_revenue_pct': round(sum(it['pct'] for it in items if it['abc'] == 'B'), 1),
                'c_revenue_pct': round(sum(it['pct'] for it in items if it['abc'] == 'C'), 1),
            },
            'currency': self._currency_payload(parsed['company'].currency_id),
        }

    def _product_sums(self, parsed, account_ids, sign=-1.0):
        """Suma (balance * sign) y nº de facturas únicas por producto."""
        if not account_ids:
            return []
        domain = self._base_domain(parsed) + [
            ('account_id', 'in', account_ids),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
        ]
        rows = self.env['account.move.line']._read_group(
            domain,
            groupby=['product_id'],
            aggregates=['balance:sum', 'move_id:count_distinct', 'partner_id:array_agg'],
        )
        out = []
        for product, balance, n_moves, partners in rows:
            pid = product.id if product else None
            val = sign * float(balance or 0.0)
            # Partners: filtrar None y deduplicar.
            partners = list({p for p in (partners or []) if p})
            out.append((pid, val, int(n_moves or 0), partners))
        return out

    def _product_quantities(self, parsed, account_ids):
        """Cantidad neta vendida por producto (apuntes de ingreso)."""
        if not account_ids:
            return {}
        domain = self._base_domain(parsed) + [
            ('account_id', 'in', account_ids),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
        ]
        rows = self.env['account.move.line']._read_group(
            domain,
            groupby=['product_id'],
            aggregates=['quantity:sum'],
        )
        return {(p.id if p else None): float(qty or 0.0) for p, qty in rows}

    # ==================================================================
    # Inteligencia de Clientes (#9)
    # ==================================================================
    @api.model
    def get_customer_intelligence(self, filters):
        """Top clientes con score 0-100 y recomendaciones."""
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        income_ids = [aid for aid, t in type_map.items() if t in ('income', 'income_other')]
        rec_ids = [aid for aid, t in type_map.items() if t == 'asset_receivable']
        limit = int(filters.get('limit') or LIMIT_DEFAULT)

        # Ingresos por partner.
        rev_by_partner = self._partner_revenue(parsed, income_ids)
        # Exposición actual y mora por partner.
        exposure = self._partner_exposure(parsed, rec_ids, side='receivable')
        # DSO y antigüedad de relación (primera factura).
        dso_map = self._partner_dso(parsed, income_ids, rec_ids)
        tenure_map = self._partner_tenure(parsed, income_ids)

        partner_ids = set(rev_by_partner) | set(exposure) | set(dso_map) | set(tenure_map)
        partner_ids.discard(None)
        if not partner_ids:
            return self._empty_entity_payload(parsed)

        names = {}
        meta = {}
        for p in self.env['res.partner'].sudo().browse(list(partner_ids)).exists():
            names[p.id] = p.display_name
            meta[p.id] = {
                'country': p.country_id.name if p.country_id else '',
                'email': p.email or '',
                'phone': p.phone or '',
            }

        # Normalizadores
        max_rev = max((rev_by_partner.get(pid, (0.0, 0, []))[0] for pid in partner_ids), default=0.0) or 1.0
        max_freq = max((rev_by_partner.get(pid, (0.0, 0, []))[1] for pid in partner_ids), default=1) or 1
        today = parsed['date_to'] or date.today()

        items = []
        for pid in partner_ids:
            rev, freq, _moves = rev_by_partner.get(pid, (0.0, 0, []))
            exp_data = exposure.get(pid, {'pending': 0.0, 'overdue': 0.0,
                                          'overdue_pct': 0.0, 'avg_days': 0.0})
            dso = float(dso_map.get(pid, 0.0))
            tenure_days = (today - tenure_map[pid]).days if pid in tenure_map and tenure_map[pid] else 0

            # Sub-scores (0..100).
            s_value = min(100.0, (rev / max_rev) * 100.0) if max_rev else 0.0
            s_freq = min(100.0, (freq / max_freq) * 100.0) if max_freq else 0.0
            # Pago: 100 si DSO<=30, 0 si DSO>=120; lineal entre medio.
            if dso <= 30:
                s_pay = 100.0
            elif dso >= 120:
                s_pay = 0.0
            else:
                s_pay = max(0.0, 100.0 - ((dso - 30.0) / 90.0 * 100.0))
            # Mora: 100 si 0% vencido; 0 si >=40% vencido.
            ov_pct = exp_data['overdue_pct']
            if ov_pct <= 0:
                s_over = 100.0
            elif ov_pct >= 40:
                s_over = 0.0
            else:
                s_over = max(0.0, 100.0 - (ov_pct / 40.0 * 100.0))
            # Antigüedad: 100 a partir de 2 años, lineal por debajo.
            s_tenure = min(100.0, (tenure_days / 730.0) * 100.0)

            score = (
                s_value * CUSTOMER_SCORE_WEIGHTS['value'] +
                s_freq * CUSTOMER_SCORE_WEIGHTS['frequency'] +
                s_pay * CUSTOMER_SCORE_WEIGHTS['payment'] +
                s_over * CUSTOMER_SCORE_WEIGHTS['overdue'] +
                s_tenure * CUSTOMER_SCORE_WEIGHTS['tenure']
            ) / 100.0

            tier = self._score_tier(score)
            recs = self._customer_recommendations(rev, ov_pct, dso, freq, tenure_days)

            items.append({
                'partner_id': pid,
                'name': names.get(pid, _('(Sin nombre)')),
                'meta': meta.get(pid, {}),
                'revenue': round(rev, 2),
                'frequency': freq,
                'dso_days': round(dso, 1),
                'pending': round(exp_data['pending'], 2),
                'overdue': round(exp_data['overdue'], 2),
                'overdue_pct': round(ov_pct, 1),
                'tenure_days': tenure_days,
                'score': round(score, 1),
                'tier': tier,
                'subscores': {
                    'value': round(s_value, 1),
                    'frequency': round(s_freq, 1),
                    'payment': round(s_pay, 1),
                    'overdue': round(s_over, 1),
                    'tenure': round(s_tenure, 1),
                },
                'recommendations': recs,
            })

        items.sort(key=lambda r: r['revenue'], reverse=True)
        total = sum(it['revenue'] for it in items)
        # Concentración (% acumulado top 5/10).
        top5_pct = sum(it['revenue'] for it in items[:5]) / total * 100.0 if total else 0.0
        top10_pct = sum(it['revenue'] for it in items[:10]) / total * 100.0 if total else 0.0
        # Alertas: clientes top con score crítico.
        alerts = [
            {
                'partner_id': it['partner_id'],
                'name': it['name'],
                'reason': _('Cliente clave con score crítico (%d/100); mora %.1f%%') % (it['score'], it['overdue_pct']),
            }
            for it in items[:20] if it['score'] < 50 and it['overdue_pct'] > 20
        ]
        return {
            'items': items[:limit],
            'total_revenue': round(total, 2),
            'partners_count': len(items),
            'concentration': {
                'top5_pct': round(top5_pct, 1),
                'top10_pct': round(top10_pct, 1),
            },
            'alerts': alerts,
            'currency': self._currency_payload(parsed['company'].currency_id),
            'tier_summary': self._tier_summary(items),
        }

    # ==================================================================
    # Inteligencia de Proveedores (#10)
    # ==================================================================
    @api.model
    def get_supplier_intelligence(self, filters):
        """Top proveedores con score y dependencia (concentración)."""
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        # Compras = COGS + EXPENSE. Proveedores se identifican por su lado
        # del débito en cuentas de gasto/COGS.
        purchase_ids = [aid for aid, t in type_map.items()
                        if t in ('expense', 'expense_direct_cost', 'expense_depreciation')]
        pay_ids = [aid for aid, t in type_map.items() if t == 'liability_payable']
        limit = int(filters.get('limit') or LIMIT_DEFAULT)

        # Compras por partner.
        pur_by_partner = self._partner_revenue(parsed, purchase_ids, sign=1.0)
        exposure = self._partner_exposure(parsed, pay_ids, side='payable')
        dpo_map = self._partner_dso(parsed, purchase_ids, pay_ids)
        tenure_map = self._partner_tenure(parsed, purchase_ids)

        partner_ids = set(pur_by_partner) | set(exposure) | set(dpo_map) | set(tenure_map)
        partner_ids.discard(None)
        if not partner_ids:
            return self._empty_entity_payload(parsed)

        names = {}
        for p in self.env['res.partner'].sudo().browse(list(partner_ids)).exists():
            names[p.id] = p.display_name

        total = sum(pur_by_partner.get(pid, (0.0, 0, []))[0] for pid in partner_ids) or 1.0
        max_pur = max((pur_by_partner.get(pid, (0.0, 0, []))[0] for pid in partner_ids), default=0.0) or 1.0
        max_freq = max((pur_by_partner.get(pid, (0.0, 0, []))[1] for pid in partner_ids), default=1) or 1
        today = parsed['date_to'] or date.today()

        items = []
        for pid in partner_ids:
            pur, freq, _moves = pur_by_partner.get(pid, (0.0, 0, []))
            exp_data = exposure.get(pid, {'pending': 0.0, 'overdue': 0.0,
                                          'overdue_pct': 0.0, 'avg_days': 0.0})
            dpo = float(dpo_map.get(pid, 0.0))
            tenure_days = (today - tenure_map[pid]).days if pid in tenure_map and tenure_map[pid] else 0
            concentration = (pur / total) * 100.0 if total else 0.0

            s_value = min(100.0, (pur / max_pur) * 100.0)
            s_freq = min(100.0, (freq / max_freq) * 100.0)
            # Pago: para proveedores invertimos lógica → DPO razonable es 30-60d.
            # >90d = riesgo de relación. <15d = pagas demasiado rápido.
            if 30 <= dpo <= 60:
                s_pay = 100.0
            elif dpo < 15 or dpo > 120:
                s_pay = 30.0
            elif dpo < 30:
                s_pay = 60.0 + (dpo - 15) / 15.0 * 40.0
            else:  # 60 < dpo <= 120
                s_pay = max(20.0, 100.0 - (dpo - 60) / 60.0 * 80.0)
            # Concentración: a menor dependencia, mayor score.
            if concentration <= 5:
                s_conc = 100.0
            elif concentration >= 40:
                s_conc = 10.0
            else:
                s_conc = max(10.0, 100.0 - (concentration - 5.0) / 35.0 * 90.0)
            s_tenure = min(100.0, (tenure_days / 730.0) * 100.0)

            score = (
                s_value * SUPPLIER_SCORE_WEIGHTS['value'] +
                s_freq * SUPPLIER_SCORE_WEIGHTS['frequency'] +
                s_pay * SUPPLIER_SCORE_WEIGHTS['payment'] +
                s_conc * SUPPLIER_SCORE_WEIGHTS['concentration'] +
                s_tenure * SUPPLIER_SCORE_WEIGHTS['tenure']
            ) / 100.0
            tier = self._score_tier(score)
            recs = self._supplier_recommendations(pur, concentration, dpo, exp_data['overdue_pct'])

            items.append({
                'partner_id': pid,
                'name': names.get(pid, _('(Sin nombre)')),
                'purchases': round(pur, 2),
                'frequency': freq,
                'dpo_days': round(dpo, 1),
                'pending': round(exp_data['pending'], 2),
                'overdue': round(exp_data['overdue'], 2),
                'overdue_pct': round(exp_data['overdue_pct'], 1),
                'concentration_pct': round(concentration, 2),
                'tenure_days': tenure_days,
                'score': round(score, 1),
                'tier': tier,
                'subscores': {
                    'value': round(s_value, 1),
                    'frequency': round(s_freq, 1),
                    'payment': round(s_pay, 1),
                    'concentration': round(s_conc, 1),
                    'tenure': round(s_tenure, 1),
                },
                'recommendations': recs,
            })
        items.sort(key=lambda r: r['purchases'], reverse=True)
        top5_pct = sum(it['purchases'] for it in items[:5]) / total * 100.0 if total else 0.0
        top10_pct = sum(it['purchases'] for it in items[:10]) / total * 100.0 if total else 0.0
        # Riesgo crítico: proveedor con >25% concentración.
        risk = [{
            'partner_id': it['partner_id'],
            'name': it['name'],
            'reason': _('Dependencia alta: %.1f%% de las compras') % it['concentration_pct'],
        } for it in items[:20] if it['concentration_pct'] >= 25]
        return {
            'items': items[:limit],
            'total_purchases': round(total, 2),
            'partners_count': len(items),
            'concentration': {
                'top5_pct': round(top5_pct, 1),
                'top10_pct': round(top10_pct, 1),
            },
            'risk_alerts': risk,
            'currency': self._currency_payload(parsed['company'].currency_id),
            'tier_summary': self._tier_summary(items),
        }

    # ==================================================================
    # Helpers comunes
    # ==================================================================
    def _empty_entity_payload(self, parsed):
        return {
            'items': [], 'total_revenue': 0.0, 'total_purchases': 0.0,
            'partners_count': 0, 'concentration': {'top5_pct': 0.0, 'top10_pct': 0.0},
            'alerts': [], 'risk_alerts': [],
            'currency': self._currency_payload(parsed['company'].currency_id),
            'tier_summary': {'champion': 0, 'good': 0, 'average': 0, 'risky': 0, 'critical': 0},
        }

    def _partner_revenue(self, parsed, account_ids, sign=-1.0):
        """Devuelve {partner_id: (importe, n_facturas, [partner_ids])}.

        Para clientes (ingresos) sign=-1; para proveedores (compras) sign=+1.
        """
        if not account_ids:
            return {}
        domain = self._base_domain(parsed) + [
            ('account_id', 'in', account_ids),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
            ('partner_id', '!=', False),
        ]
        rows = self.env['account.move.line']._read_group(
            domain,
            groupby=['partner_id'],
            aggregates=['balance:sum', 'move_id:count_distinct'],
        )
        out = {}
        for partner, balance, n_moves in rows:
            pid = partner.id if partner else None
            val = sign * float(balance or 0.0)
            out[pid] = (val, int(n_moves or 0), [])
        return out

    def _partner_exposure(self, parsed, account_ids, side='receivable'):
        """Saldo pendiente y vencido por partner al cierre.

        Usa ``amount_residual`` (signo según account_type) e identifica el
        vencimiento por ``date_maturity`` o ``date``.
        """
        if not account_ids:
            return {}
        on_date = parsed['date_to']
        sign = 1.0 if side == 'receivable' else -1.0
        domain = self._base_domain(parsed) + [
            ('account_id', 'in', account_ids),
            ('amount_residual', '!=', 0.0),
            ('date', '<=', on_date),
            ('partner_id', '!=', False),
        ]
        # Para esta consulta necesitamos el detalle (no agregable directamente
        # porque overdue depende de date_maturity vs on_date).
        lines = self.env['account.move.line'].search_read(
            domain, ['partner_id', 'amount_residual', 'date_maturity', 'date'],
        )
        agg = defaultdict(lambda: {'pending': 0.0, 'overdue': 0.0, 'wdays': 0.0})
        for ln in lines:
            pid = ln['partner_id'][0] if ln['partner_id'] else None
            if not pid:
                continue
            res = sign * float(ln['amount_residual'] or 0.0)
            maturity = ln.get('date_maturity') or ln.get('date')
            days_overdue = (on_date - maturity).days if maturity else 0
            agg[pid]['pending'] += res
            if days_overdue > 0:
                agg[pid]['overdue'] += res
            agg[pid]['wdays'] += res * max(0, days_overdue)
        out = {}
        for pid, vals in agg.items():
            pending = vals['pending']
            overdue = vals['overdue']
            avg_days = (vals['wdays'] / pending) if pending else 0.0
            # Clamp [0, 100]: si pending<=0 (todo a favor) o overdue<0 (saldo
            # vencido a favor del partner) la mora no aplica → 0%.
            if pending > 0 and overdue > 0:
                ov_pct = min(100.0, overdue / pending * 100.0)
            else:
                ov_pct = 0.0
                overdue = max(0.0, overdue)
            out[pid] = {
                'pending': pending,
                'overdue': overdue,
                'overdue_pct': ov_pct,
                'avg_days': max(0.0, avg_days),
            }
        return out

    def _partner_dso(self, parsed, income_ids, rec_ids):
        """DSO simplificado = (saldo CxC promedio / ingresos del periodo) × días.

        Por partner. Cuando no hay ingresos en el periodo devuelve 0.
        """
        if not income_ids or not rec_ids:
            return {}
        df, dt = parsed['date_from'], parsed['date_to']
        days = max(1, (dt - df).days + 1)
        # Saldo CxC al cierre por partner.
        domain_rec = self._base_domain(parsed) + [
            ('account_id', 'in', rec_ids),
            ('date', '<=', dt),
            ('partner_id', '!=', False),
        ]
        rec_rows = self.env['account.move.line']._read_group(
            domain_rec, groupby=['partner_id'], aggregates=['balance:sum'],
        )
        rec_map = {p.id: float(b or 0.0) for p, b in rec_rows if p}
        # Ingresos del período por partner.
        rev = self._partner_revenue(parsed, income_ids, sign=-1.0)
        out = {}
        for pid, info in rev.items():
            revenue = info[0]
            if revenue <= 0:
                continue
            balance = rec_map.get(pid, 0.0)
            if balance <= 0:
                continue
            out[pid] = (balance / revenue) * days
        return out

    def _partner_tenure(self, parsed, account_ids):
        """Fecha de la primera factura del partner (cualquier compañía visible)."""
        if not account_ids:
            return {}
        domain = self._base_domain(parsed) + [
            ('account_id', 'in', account_ids),
            ('partner_id', '!=', False),
        ]
        # Importante: SIN filtro de fechas (queremos histórico completo).
        rows = self.env['account.move.line']._read_group(
            domain, groupby=['partner_id'], aggregates=['date:min'],
        )
        return {p.id: d for p, d in rows if p and d}

    def _score_tier(self, score):
        if score >= 80:
            return 'champion'
        if score >= 65:
            return 'good'
        if score >= 50:
            return 'average'
        if score >= 35:
            return 'risky'
        return 'critical'

    def _tier_summary(self, items):
        out = {'champion': 0, 'good': 0, 'average': 0, 'risky': 0, 'critical': 0}
        for it in items:
            out[it['tier']] = out.get(it['tier'], 0) + 1
        return out

    def _customer_recommendations(self, revenue, ov_pct, dso, freq, tenure_days):
        recs = []
        if ov_pct > 30:
            recs.append(_('Activar gestión de cobranza intensiva: %.1f%% de saldo vencido.') % ov_pct)
        if dso > 60:
            recs.append(_('Negociar nuevos términos: el DSO (%.0f días) está por encima del estándar.') % dso)
        if revenue > 0 and freq <= 2:
            recs.append(_('Cliente de baja frecuencia: evaluar campaña de re-engagement.'))
        if tenure_days > 1095 and ov_pct < 5:
            recs.append(_('Cliente leal: candidato a programa premium o descuento por volumen.'))
        if not recs:
            recs.append(_('Comportamiento dentro de parámetros saludables.'))
        return recs

    def _supplier_recommendations(self, purchases, concentration, dpo, ov_pct):
        recs = []
        if concentration >= 25:
            recs.append(_('Reducir dependencia: este proveedor concentra el %.1f%% de las compras.') % concentration)
        if dpo < 15 and purchases > 0:
            recs.append(_('Negociar términos de pago más largos: estamos pagando muy rápido (%.0f días).') % dpo)
        if dpo > 90:
            recs.append(_('Riesgo de relación: el plazo de pago efectivo (%.0f días) puede afectar la entrega.') % dpo)
        if ov_pct > 0:
            recs.append(_('Hay saldos vencidos pendientes con este proveedor.'))
        if not recs:
            recs.append(_('Relación saludable: continuar con los términos actuales.'))
        return recs
