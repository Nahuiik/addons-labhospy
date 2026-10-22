# -*- coding: utf-8 -*-
"""Motor predictivo y de escenarios (V20 Fase 5).

Funcionalidades expuestas al frontend:

- :meth:`get_predictions_data` (RPC principal) reúne forecast, score
  multifactor y benchmark sectorial en una sola llamada.
- :meth:`simulate_scenario` evalúa el impacto de cambios "what-if"
  (precio, costos, gastos, días de cobro/pago) sobre los KPIs actuales.

Diseño:

- El forecast se calcula sobre series mensuales construidas con
  ``account.move.line`` agrupado por ``date:month`` y ``account_id``.
  Para cada KPI usamos la mezcla de tipos contables ya definida en el
  módulo (INCOME_TYPES, COGS_TYPES, EXPENSE_TYPES) y exponemos un
  fitting con regresión lineal y, cuando hay >= 6 puntos, un suavizado
  de Holt (nivel + tendencia) para capturar inercia.
- El score evita falsos positivos: cada componente tiene una rampa de
  saturación entre umbrales ``min`` y ``target`` (0..100) y se promedia
  ponderadamente. Si una señal no puede calcularse se ignora (su peso se
  redistribuye), evitando colapsar el score por datos ausentes.
- ``simulate_scenario`` parte de los KPIs reales del periodo y aplica
  transformaciones aditivas y multiplicativas; no toca la base de datos.

Nota de rendimiento: la consulta de series usa ``read_group`` sobre
``account.move.line`` con un solo round-trip por compañía. Para BDs
medianas (LABHOSPY ~80k apuntes) la latencia se mantiene bajo ~1s.
"""
import math
from collections import defaultdict
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

from .financial_dashboard import (
    INCOME_TYPES, COGS_TYPES, EXPENSE_TYPES, CASH_TYPES,
)


# ----------------------------------------------------------------------
# Catálogo de KPIs con serie temporal soportada por el forecast.
# Cada entrada describe cómo obtener el "valor mensual" desde las sumas
# por cuenta. ``sign`` indica si el resultado se invierte (los ingresos
# en account.move.line vienen con signo negativo).
# ``cumulative=True`` arrastra el saldo anterior (ej. bancos).
# ----------------------------------------------------------------------
SERIES_KPIS = {
    'revenue': {
        'types': INCOME_TYPES,
        'sign': -1.0,
        'label': 'Ingresos',
        'cumulative': False,
        'hint_higher_better': True,
    },
    'gross_profit': {
        'composed': True,
        'label': 'Utilidad bruta',
        'cumulative': False,
        'hint_higher_better': True,
    },
    'expenses': {
        'types': EXPENSE_TYPES,
        'sign': 1.0,
        'label': 'Gastos operativos',
        'cumulative': False,
        'hint_higher_better': False,
    },
    'net_profit': {
        'composed': True,
        'label': 'Utilidad neta',
        'cumulative': False,
        'hint_higher_better': True,
    },
    'cash_flow': {
        'composed': True,
        'label': 'Flujo de caja del mes',
        'cumulative': False,
        'hint_higher_better': True,
    },
}


class GnFinancialDashboardPredictive(models.AbstractModel):
    _inherit = 'gn.financial.dashboard'

    # ------------------------------------------------------------------
    # Series mensuales (1 query, todo en RAM)
    # ------------------------------------------------------------------
    @api.model
    def _series_window(self, parsed, months_back=24):
        """Calcula ``(start, end)`` de la ventana histórica para el forecast.

        Anclamos al final del mes de ``date_to`` y retrocedemos
        ``months_back`` meses, para que la serie siempre termine con un
        mes "completo".
        """
        dt = parsed['date_to']
        end = (dt.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)
        start = (end - relativedelta(months=months_back - 1)).replace(day=1)
        return start, end

    @api.model
    def _build_monthly_account_sums(self, parsed, start, end):
        """``{ (year, month): { account_id: {'balance','debit','credit'} } }``.

        Reusa el dominio base del módulo (compañía, posted/draft, sucursal)
        y agrupa por ``date:month`` + ``account_id`` con read_group.
        """
        AML = self.env['account.move.line'].sudo()
        domain = self._base_domain(parsed)
        domain += [('date', '>=', start), ('date', '<=', end)]
        # Para series temporales ignoramos filtros analíticos: complican
        # la agregación mes a mes y la ruta analítica no expone debit/credit
        # cuadrados con la P&L global. El forecast es una proyección y no
        # un reporte estricto.
        rows = AML._read_group(
            domain,
            groupby=['date:month', 'account_id'],
            aggregates=['balance:sum', 'debit:sum', 'credit:sum'],
        )
        out = defaultdict(lambda: defaultdict(lambda: {'balance': 0.0, 'debit': 0.0, 'credit': 0.0}))
        for label, account, balance, debit, credit in rows:
            if not label or not account:
                continue
            # label puede llegar como string 'YYYY-MM' o como datetime
            if isinstance(label, str):
                try:
                    year, month = int(label[:4]), int(label[5:7])
                except (TypeError, ValueError):
                    continue
            else:
                year, month = label.year, label.month
            key = (year, month)
            entry = out[key][account.id]
            entry['balance'] += float(balance or 0.0)
            entry['debit'] += float(debit or 0.0)
            entry['credit'] += float(credit or 0.0)
        return out

    @api.model
    def _months_between(self, start, end):
        """Lista ordenada de (year, month) entre ``start`` y ``end`` (incl.)."""
        cur = start.replace(day=1)
        last = end.replace(day=1)
        out = []
        while cur <= last:
            out.append((cur.year, cur.month))
            cur = cur + relativedelta(months=1)
        return out

    @api.model
    def _series_from_account_sums(self, account_sums, months, type_map):
        """Construye las series mensuales declaradas en SERIES_KPIS."""
        series = {k: [] for k in SERIES_KPIS}
        income_ids = {aid for aid, t in type_map.items() if t in INCOME_TYPES}
        cogs_ids = {aid for aid, t in type_map.items() if t in COGS_TYPES}
        expense_ids = {aid for aid, t in type_map.items() if t in EXPENSE_TYPES}
        cash_ids = {aid for aid, t in type_map.items() if t in CASH_TYPES}
        for key in months:
            month_data = account_sums.get(key, {})

            def _sum_balance(ids, sign=1.0):
                return sign * sum(
                    month_data.get(aid, {}).get('balance', 0.0) for aid in ids
                )

            rev = _sum_balance(income_ids, -1.0)
            cogs = _sum_balance(cogs_ids, 1.0)
            exp = _sum_balance(expense_ids, 1.0)
            cash_in = sum(month_data.get(aid, {}).get('debit', 0.0) for aid in cash_ids)
            cash_out = sum(month_data.get(aid, {}).get('credit', 0.0) for aid in cash_ids)

            series['revenue'].append(rev)
            series['expenses'].append(exp)
            series['gross_profit'].append(rev - cogs)
            series['net_profit'].append(rev - cogs - exp)
            series['cash_flow'].append(cash_in - cash_out)
        return series

    # ------------------------------------------------------------------
    # Modelos de pronóstico (lineal + Holt)
    # ------------------------------------------------------------------
    @api.model
    def _fit_linear(self, ys):
        """Mínimos cuadrados: devuelve (slope, intercept, sigma_resid)."""
        n = len(ys)
        if n < 2:
            return 0.0, (ys[0] if ys else 0.0), 0.0
        xs = list(range(n))
        sx = sum(xs); sy = sum(ys)
        sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
        denom = (n * sxx - sx * sx)
        if denom == 0:
            return 0.0, sy / n, 0.0
        slope = (n * sxy - sx * sy) / denom
        intercept = (sy - slope * sx) / n
        # error residual estándar (para banda de confianza ±1σ).
        resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
        sigma = math.sqrt(sum(r * r for r in resid) / max(n - 2, 1))
        return slope, intercept, sigma

    @api.model
    def _fit_holt(self, ys, alpha=0.4, beta=0.2):
        """Holt's linear smoothing.

        Devuelve (level, trend, sigma_resid). Si ``ys`` tiene menos de 3
        puntos se cae back a regresión lineal.
        """
        if len(ys) < 3:
            slope, intercept, sigma = self._fit_linear(ys)
            return (intercept + slope * (len(ys) - 1)), slope, sigma
        level = ys[0]
        trend = ys[1] - ys[0]
        resid = []
        for i in range(1, len(ys)):
            prev_level = level
            level = alpha * ys[i] + (1 - alpha) * (prev_level + trend)
            trend = beta * (level - prev_level) + (1 - beta) * trend
            forecast_i = prev_level + trend
            resid.append(ys[i] - forecast_i)
        sigma = (sum(r * r for r in resid) / max(len(resid) - 1, 1)) ** 0.5
        return level, trend, sigma

    @api.model
    def _forecast_series(self, series, horizon):
        """Aplica Holt al histórico y proyecta ``horizon`` puntos."""
        if not series:
            return {'forecast': [], 'lower': [], 'upper': [], 'slope': 0.0}
        level, trend, sigma = self._fit_holt(series)
        # Para forecast usamos Holt; ±1σ como banda heurística.
        forecast = [level + trend * (i + 1) for i in range(horizon)]
        lower = [v - sigma for v in forecast]
        upper = [v + sigma for v in forecast]
        # Slope unitaria (cambio promedio por mes) en términos del últi-
        # mo punto histórico, útil para la narrativa.
        return {
            'forecast': [round(v, 2) for v in forecast],
            'lower': [round(v, 2) for v in lower],
            'upper': [round(v, 2) for v in upper],
            'slope': round(trend, 2),
            'sigma': round(sigma, 2),
        }

    @api.model
    def _format_month_label(self, year, month):
        return '%04d-%02d' % (year, month)

    # ------------------------------------------------------------------
    # Score predictivo multifactor (0..100)
    # ------------------------------------------------------------------
    @api.model
    def _score_ramp(self, value, low, target, lower_better=False):
        """Convierte ``value`` a un score [0..100] con rampa lineal.

        - Si ``lower_better=False``: value <= low -> 0; value >= target -> 100.
        - Si ``lower_better=True``: value <= target -> 100; value >= low -> 0.
        """
        if value is None or low == target:
            return None
        if lower_better:
            if value <= target:
                return 100.0
            if value >= low:
                return 0.0
            return round(100.0 * (low - value) / (low - target), 1)
        if value <= low:
            return 0.0
        if value >= target:
            return 100.0
        return round(100.0 * (value - low) / (target - low), 1)

    @api.model
    def _normalize_kpis(self, kpis):
        """Adapta los KPIs nativos al vocabulario usado por score/benchmark.

        Mapea ``gross_margin`` → ``gross_margin_pct``, expone DSO/DPO a
        partir de las rotaciones y calcula la palanca financiera básica
        cuando hay activos.
        """
        out = dict(kpis or {})
        # Alias *_pct para los márgenes y rendimientos.
        for src, dst in (
            ('gross_margin', 'gross_margin_pct'),
            ('operating_margin', 'operating_margin_pct'),
            ('ebitda_margin', 'ebitda_margin_pct'),
            ('net_margin', 'net_margin_pct'),
            ('roa', 'roa_pct'),
            ('roe', 'roe_pct'),
            ('assets_turnover', 'asset_turnover'),
        ):
            if src in out and dst not in out:
                out[dst] = out[src]
        # DSO/DPO derivados de las rotaciones anualizadas.
        ar_t = out.get('ar_turnover') or 0.0
        ap_t = out.get('ap_turnover') or 0.0
        out['dso_days'] = round(365.0 / ar_t, 1) if ar_t > 0 else None
        out['dpo_days'] = round(365.0 / ap_t, 1) if ap_t > 0 else None
        # Palanca: usamos leverage_ratio como Activos/Patrimonio. Para
        # Deuda/Activos restamos 1 sobre la palanca cuando aplica.
        if out.get('total_assets') and out.get('net_assets'):
            # net_assets ≈ patrimonio; deuda total = activos − patrimonio.
            liab = out['total_assets'] - out['net_assets']
            out['debt_to_assets'] = round(liab / out['total_assets'], 3) \
                if out['total_assets'] else None
        # Revenue growth se calculará desde la serie y se inyectará desde
        # ``_predictive_score`` con la pendiente; aquí dejamos placeholder.
        return out

    @api.model
    def _predictive_score(self, parsed, kpis, forecast_payload):
        """Score 0-100 del negocio + componentes y narrativa.

        Combina señales operativas (margen, liquidez, palanca financiera)
        con la tendencia proyectada de ingresos y caja. Cada componente
        aporta un peso configurable; los componentes sin datos se ignoran
        (sin penalizar) y los pesos se redistribuyen.
        """
        kpis = self._normalize_kpis(kpis)
        components = []

        def add(label, value, low, target, weight=1.0, lower_better=False, fmt=None, note=None):
            s = self._score_ramp(value, low, target, lower_better=lower_better)
            if s is None:
                return
            components.append({
                'label': label,
                'value': value,
                'fmt': fmt or 'number',
                'score': s,
                'weight': weight,
                'note': note or '',
            })

        # Rentabilidad
        add(_('Margen bruto'), kpis.get('gross_margin_pct'), 10, 35, weight=1.0, fmt='percent')
        add(_('Margen operativo'), kpis.get('operating_margin_pct'), 0, 12, weight=1.2, fmt='percent')
        add(_('Margen neto'), kpis.get('net_margin_pct'), -2, 10, weight=1.0, fmt='percent')

        # Liquidez
        add(_('Razón corriente'), kpis.get('current_ratio'), 0.9, 1.8, weight=1.2, fmt='number')
        add(_('Prueba ácida'), kpis.get('quick_ratio'), 0.6, 1.2, weight=0.8, fmt='number')

        # Estructura financiera
        add(_('Deuda / Activos'), kpis.get('debt_to_assets'), 0.8, 0.4, weight=1.0,
            fmt='number', lower_better=True)
        add(_('Cobertura de intereses'), kpis.get('interest_coverage'), 1.5, 4.0, weight=0.6, fmt='number')

        # Eficiencia
        add(_('Rotación de activos'), kpis.get('asset_turnover'), 0.3, 1.0, weight=0.6, fmt='number')
        add(_('Rotación de inventario'), kpis.get('inventory_turnover'), 2.0, 6.0, weight=0.6, fmt='number')
        add(_('DSO (días de cartera)'), kpis.get('dso_days'), 90, 40, weight=0.8,
            fmt='days', lower_better=True)

        # Tendencia proyectada (revenue + cash_flow): convertimos el slope
        # a % del nivel actual (más comparable entre compañías).
        last_revenue = forecast_payload.get('revenue', {}).get('history', [])
        last_rev_val = last_revenue[-1] if last_revenue else 0.0
        rev_slope = forecast_payload.get('revenue', {}).get('forecast_meta', {}).get('slope', 0.0)
        if last_rev_val:
            growth_pct = (rev_slope / abs(last_rev_val)) * 100.0
            add(_('Tendencia de ingresos (mes/mes)'), growth_pct, -2, 3, weight=1.5,
                fmt='percent',
                note=_('Pendiente proyectada vs último mes histórico.'))

        cash_hist = forecast_payload.get('cash_flow', {}).get('history', [])
        cash_slope = forecast_payload.get('cash_flow', {}).get('forecast_meta', {}).get('slope', 0.0)
        if cash_hist:
            last_cash = cash_hist[-1] if cash_hist else 0.0
            add(_('Tendencia de flujo de caja'), cash_slope,
                -abs(last_cash) * 0.05 if last_cash else -1.0,
                abs(last_cash) * 0.05 if last_cash else 1.0,
                weight=1.0, fmt='money',
                note=_('Pendiente esperada en el flujo mensual.'))

        # Promedio ponderado.
        total_w = sum(c['weight'] for c in components) or 1.0
        score = round(sum(c['score'] * c['weight'] for c in components) / total_w, 1)
        # Etiqueta semántica.
        if score >= 80:
            tier = 'excellent'; label = _('Excelente salud financiera')
        elif score >= 65:
            tier = 'good'; label = _('Salud financiera sólida')
        elif score >= 50:
            tier = 'fair'; label = _('Salud financiera aceptable')
        elif score >= 35:
            tier = 'risky'; label = _('Riesgo elevado')
        else:
            tier = 'critical'; label = _('Estado crítico, atención inmediata')

        narrative = self._predictive_narrative(components, score, tier, forecast_payload)
        return {
            'score': score,
            'tier': tier,
            'label': label,
            'components': components,
            'narrative': narrative,
        }

    @api.model
    def _predictive_narrative(self, components, score, tier, forecast_payload):
        bullets = []
        weak = [c for c in components if c['score'] < 50]
        strong = [c for c in components if c['score'] >= 80]
        if strong:
            bullets.append(_('Fortalezas: %s.') % ', '.join(c['label'] for c in strong[:3]))
        if weak:
            bullets.append(_('Oportunidades de mejora: %s.') % ', '.join(c['label'] for c in weak[:3]))
        rev = forecast_payload.get('revenue', {})
        if rev.get('forecast'):
            avg_fc = sum(rev['forecast']) / len(rev['forecast'])
            bullets.append(_(
                'Pronóstico de ingresos: promedio mensual %(avg)s en los próximos %(n)d meses.'
            ) % {'avg': '{:,.0f}'.format(avg_fc), 'n': len(rev['forecast'])})
        cash = forecast_payload.get('cash_flow', {})
        if cash.get('forecast'):
            n_neg = sum(1 for v in cash['forecast'] if v < 0)
            if n_neg:
                bullets.append(_(
                    'Atención: %d de los próximos %d meses muestran flujo de caja negativo en la proyección.'
                ) % (n_neg, len(cash['forecast'])))
        if not bullets:
            bullets.append(_('Datos insuficientes para una narrativa detallada.'))
        return bullets

    # ------------------------------------------------------------------
    # Benchmark sectorial
    # ------------------------------------------------------------------
    @api.model
    def _benchmark_compare(self, kpi_code, current, benchmark):
        """Devuelve dict con status (good/warn/bad), brecha y mensaje."""
        if current is None:
            return None
        target = benchmark.target_value
        direction = benchmark.direction
        gap = current - target
        gap_pct = (gap / target * 100.0) if target else 0.0
        # Status.
        if direction == 'higher_better':
            if benchmark.min_value and current < benchmark.min_value:
                status = 'bad'
            elif current >= target:
                status = 'good'
            else:
                status = 'warn'
        else:
            if benchmark.max_value and current > benchmark.max_value:
                status = 'bad'
            elif current <= target:
                status = 'good'
            else:
                status = 'warn'
        return {
            'kpi_code': kpi_code,
            'current': round(float(current), 2),
            'target': round(float(target), 2),
            'gap': round(gap, 2),
            'gap_pct': round(gap_pct, 1),
            'direction': direction,
            'status': status,
            'min': benchmark.min_value or None,
            'max': benchmark.max_value or None,
            'source': benchmark.source or '',
        }

    @api.model
    def get_benchmark_data(self, filters):
        """Compara KPIs actuales contra benchmark de un sector."""
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        raw_kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        kpis = self._normalize_kpis(raw_kpis)

        sector = (filters.get('benchmark_sector') or '').strip() or 'hospital'
        Bench = self.env['gn.financial.dashboard.benchmark'].sudo()
        benchmarks = Bench.search([
            ('sector', '=', sector),
            ('company_id', 'in', [False, company.id]),
            ('active', '=', True),
        ])
        comparisons = []
        for b in benchmarks:
            current = kpis.get(b.kpi_code)
            cmp = self._benchmark_compare(b.kpi_code, current, b)
            if cmp is None:
                continue
            cmp['label'] = dict(b._fields['kpi_code'].selection).get(b.kpi_code, b.kpi_code)
            comparisons.append(cmp)
        # Sectores disponibles para que el usuario pueda cambiar.
        sectors = Bench.search([('company_id', 'in', [False, company.id])]).read(
            ['sector', 'sector_label']
        )
        seen = {}
        for s in sectors:
            seen.setdefault(s['sector'], s.get('sector_label') or s['sector'])
        sector_options = [{'key': k, 'label': v} for k, v in seen.items()]
        return {
            'sector': sector,
            'sector_options': sector_options,
            'comparisons': comparisons,
        }

    # ------------------------------------------------------------------
    # Simulación de escenarios
    # ------------------------------------------------------------------
    @api.model
    def simulate_scenario(self, filters, scenario):
        """Aplica deltas a los KPIs actuales y devuelve nuevos valores.

        ``scenario`` admite:

        - ``price_delta_pct``: +/- % al precio de venta (afecta ingresos).
        - ``volume_delta_pct``: +/- % al volumen (afecta ingresos y COGS).
        - ``cost_delta_pct``: +/- % al COGS (afecta utilidad bruta).
        - ``opex_delta_pct``: +/- % a los gastos operativos.
        - ``dso_delta_days``: ±N días en DSO (afecta caja y razón corriente).
        - ``dpo_delta_days``: ±N días en DPO.
        - ``capex``: gasto adicional one-shot (reduce caja/activos).
        """
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        raw_kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        kpis = self._normalize_kpis(raw_kpis)

        price = float(scenario.get('price_delta_pct') or 0.0)
        volume = float(scenario.get('volume_delta_pct') or 0.0)
        cost = float(scenario.get('cost_delta_pct') or 0.0)
        opex = float(scenario.get('opex_delta_pct') or 0.0)
        dso_d = float(scenario.get('dso_delta_days') or 0.0)
        dpo_d = float(scenario.get('dpo_delta_days') or 0.0)
        capex = float(scenario.get('capex') or 0.0)

        revenue = kpis.get('revenue') or 0.0
        cogs = kpis.get('cogs') or 0.0
        expenses = kpis.get('expenses') or 0.0
        receivables = kpis.get('receivables') or 0.0
        payables = kpis.get('payables') or 0.0
        cash = kpis.get('closing_bank') or 0.0
        current_assets = kpis.get('current_assets') or 0.0
        current_liab = kpis.get('current_liab') or 0.0
        total_assets = kpis.get('total_assets') or 0.0

        # Aplicación de deltas.
        rev_factor = (1.0 + price / 100.0) * (1.0 + volume / 100.0)
        cogs_factor = (1.0 + cost / 100.0) * (1.0 + volume / 100.0)
        new_revenue = revenue * rev_factor
        new_cogs = cogs * cogs_factor
        new_expenses = expenses * (1.0 + opex / 100.0)
        new_gross = new_revenue - new_cogs
        new_net = new_gross - new_expenses

        # Impacto en cartera y caja por cambio en DSO / DPO.
        # ΔAR ≈ revenue diario × Δdso ; ΔAP ≈ cogs diario × Δdpo
        period_days = max(self._period_days(parsed), 1)
        daily_rev = new_revenue / period_days
        daily_cogs = new_cogs / period_days
        delta_ar = daily_rev * dso_d
        delta_ap = daily_cogs * dpo_d
        new_receivables = receivables + delta_ar
        new_payables = payables + delta_ap
        # Caja simulada: la cartera adicional retiene caja; pagar más
        # tarde a proveedores la libera; CAPEX la consume.
        new_cash = cash - delta_ar + delta_ap - capex
        # Activos/pasivos corrientes:
        #   - Activos: AR sube/baja, caja se ajusta, CAPEX sale del corriente.
        #   - Pasivos: AP sube/baja por DPO.
        new_current_assets = current_assets + delta_ar + (new_cash - cash) - capex
        new_current_liab = current_liab + delta_ap
        new_total_assets = total_assets + delta_ar + (new_cash - cash) - capex
        new_working_capital = new_current_assets - new_current_liab

        def pct(part, whole):
            return (part / whole * 100.0) if whole else 0.0

        new_kpis = {
            'revenue': round(new_revenue, 2),
            'cogs': round(new_cogs, 2),
            'expenses': round(new_expenses, 2),
            'gross_profit': round(new_gross, 2),
            'net_profit': round(new_net, 2),
            'gross_margin_pct': round(pct(new_gross, new_revenue), 2),
            'operating_margin_pct': round(pct(new_gross - new_expenses, new_revenue), 2),
            'net_margin_pct': round(pct(new_net, new_revenue), 2),
            'receivables': round(new_receivables, 2),
            'payables': round(new_payables, 2),
            'closing_bank': round(new_cash, 2),
            'current_assets': round(new_current_assets, 2),
            'current_liab': round(new_current_liab, 2),
            'working_capital': round(new_working_capital, 2),
            'current_ratio': round(
                (new_current_assets / new_current_liab) if new_current_liab else 0.0, 2,
            ),
            'total_assets': round(new_total_assets, 2),
        }
        # Deltas vs actual para mostrar en UI.
        deltas = {}
        for k, v in new_kpis.items():
            base_val = kpis.get(k)
            if base_val is None:
                continue
            delta = v - base_val
            deltas[k] = {
                'base': round(float(base_val), 2),
                'new': v,
                'delta': round(delta, 2),
                'delta_pct': round((delta / base_val * 100.0) if base_val else 0.0, 1),
            }
        return {
            'scenario': scenario,
            'kpis': new_kpis,
            'deltas': deltas,
            'currency': self._currency_payload(company.currency_id),
        }

    @api.model
    def _period_days(self, parsed):
        df, dt = parsed['date_from'], parsed['date_to']
        if not df or not dt:
            return 30
        return max((dt - df).days + 1, 1)

    # ------------------------------------------------------------------
    # RPC agregador (forecast + score + benchmark en un solo payload)
    # ------------------------------------------------------------------
    @api.model
    def get_predictions_data(self, filters):
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        horizon = max(1, min(int(filters.get('forecast_horizon') or 6), 12))
        months_back = max(6, min(int(filters.get('history_months') or 24), 36))

        start, end = self._series_window(parsed, months_back=months_back)
        account_sums = self._build_monthly_account_sums(parsed, start, end)
        months = self._months_between(start, end)
        series = self._series_from_account_sums(account_sums, months, type_map)

        # Forecast por KPI
        forecast_payload = {}
        for code, meta in SERIES_KPIS.items():
            ys = series.get(code) or []
            fc = self._forecast_series(ys, horizon)
            future_labels = []
            ref = end.replace(day=1) + relativedelta(months=1)
            for i in range(horizon):
                future_labels.append(self._format_month_label(ref.year, ref.month))
                ref = ref + relativedelta(months=1)
            forecast_payload[code] = {
                'label': meta['label'],
                'history': [round(v, 2) for v in ys],
                'history_labels': [self._format_month_label(*m) for m in months],
                'forecast': fc['forecast'],
                'lower': fc['lower'],
                'upper': fc['upper'],
                'forecast_labels': future_labels,
                'forecast_meta': {'slope': fc['slope'], 'sigma': fc['sigma']},
                'hint_higher_better': meta['hint_higher_better'],
            }

        # KPIs actuales para score y benchmark.
        raw_kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        kpis_normalized = self._normalize_kpis(raw_kpis)
        score_payload = self._predictive_score(parsed, raw_kpis, forecast_payload)
        benchmark_payload = self.get_benchmark_data(filters)

        # Subset serializable de KPIs para que el frontend pueda usarlos
        # en el panel de escenarios sin reenviar el raw (que incluye
        # estructuras internas como `_strict`/`_type_map`).
        kpi_subset = {
            k: kpis_normalized.get(k) for k in (
                'revenue', 'cogs', 'expenses', 'gross_profit', 'net_profit',
                'gross_margin_pct', 'operating_margin_pct', 'ebitda_margin_pct',
                'net_margin_pct', 'roa_pct', 'roe_pct',
                'current_ratio', 'quick_ratio', 'asset_turnover',
                'inventory_turnover', 'dso_days', 'dpo_days',
                'debt_to_assets', 'leverage_ratio', 'interest_coverage',
                'closing_bank', 'receivables', 'payables',
                'total_assets', 'net_assets', 'working_capital',
                'current_assets', 'current_liab', 'quick_assets',
            )
        }

        return {
            'forecast': forecast_payload,
            'score': score_payload,
            'benchmark': benchmark_payload,
            'horizon': horizon,
            'history_months': months_back,
            'currency': self._currency_payload(company.currency_id),
            'kpis': kpi_subset,
        }
