# -*- coding: utf-8 -*-
"""Motor de scoring financiero explicable.

Calcula a partir de los KPIs, cartera (aging), tendencias y calidad de datos:

- ``categories``: 6 categorías (rentabilidad, liquidez, flujo, cobranza,
  endeudamiento, calidad de datos), cada una con un puntaje 0-100, su aporte
  (en puntos) al score global ponderado y los criterios que lo conforman
  (con su signo y peso).
- ``score`` global ponderado 0-100, ``level`` y ``label``.
- ``risk`` 0-100 (5 niveles) que alimenta el velocímetro.
- ``radar`` con 8 ejes 0-100 (las 6 categorías + capital de trabajo +
  crecimiento) para identificar fortalezas y debilidades.
- ``recommendations`` y ``decisions``: lista priorizada de acciones derivadas
  de los criterios incumplidos con impacto económico estimado.

El motor está desacoplado del resto del backend (sin dependencias de
account.move.line) para poder reutilizarse desde el dashboard, los reportes
PDF/Excel y futuras capas (p. ej. IA o explicaciones automáticas).
"""
from odoo import _, api, models


# Pesos relativos de cada categoría dentro del score global (suman 100).
CATEGORY_WEIGHTS = {
    'profitability': 25,
    'liquidity': 18,
    'cashflow': 17,
    'collection': 15,
    'leverage': 15,
    'data_quality': 10,
}

# Etiquetas legibles de cada categoría.
CATEGORY_LABELS = {
    'profitability': 'Rentabilidad',
    'liquidity': 'Liquidez',
    'cashflow': 'Flujo de caja',
    'collection': 'Cobranza',
    'leverage': 'Endeudamiento',
    'data_quality': 'Calidad de datos',
}

# Mapeo level (5 estados) -> etiqueta para el velocímetro y el score.
RISK_LEVELS = [
    (80, 'very_low', 'Muy bajo'),
    (60, 'low', 'Bajo'),
    (40, 'moderate', 'Moderado'),
    (20, 'high', 'Alto'),
    (0, 'critical', 'Crítico'),
]


class GnFinancialScoringEngine(models.AbstractModel):
    """Motor reutilizable de cálculo del score financiero explicable."""

    _name = 'gn.financial.dashboard.scoring'
    _description = 'Motor de scoring financiero explicable'

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    @api.model
    def compute(self, kpis, aging, thresholds, trends=None, data_quality=None):
        """Devuelve el desglose completo del score.

        :param kpis: dict del modelo ``gn.financial.dashboard`` (revenue,
            net_profit, net_margin, current_ratio, working_capital,
            cash_surplus, payables, total_assets, etc.).
        :param aging: dict con keys ``receivable`` y ``payable`` (cada uno
            con ``total``, ``overdue``, ``over_120`` y ``values``).
        :param thresholds: dict de la configuración (mismas keys que hoy:
            min_net_margin, max_overdue_receivable_pct, etc.).
        :param trends: dict opcional con direcciones por KPI (ver
            ``gn.financial.dashboard._trends``).
        :param data_quality: dict opcional con la salida de
            ``_data_quality`` (lista ``checks``).
        """
        categories = self._build_categories(
            kpis, aging, thresholds, data_quality)
        score, level, label = self._global_score(categories)
        risk = self._risk_indicator(score, categories)
        radar = self._radar(categories, kpis, trends)
        recommendations = self._recommendations(categories, kpis, aging)
        decisions = self._decisions(recommendations)
        # Alertas planas compatibles con el formato anterior para no romper
        # el código que ya consume ``health['alerts']`` (PDF/Excel/UI).
        alerts = self._flatten_alerts(categories)
        return {
            'score': score,
            'level': level,
            'label': _(label),
            'categories': categories,
            'risk': risk,
            'radar': radar,
            'recommendations': recommendations,
            'decisions': decisions,
            'alerts': alerts,
        }

    # ------------------------------------------------------------------
    # Categorías
    # ------------------------------------------------------------------
    def _build_categories(self, kpis, aging, thresholds, data_quality):
        """Devuelve la lista de categorías con su puntaje y criterios.

        Cada categoría arranca en 100 y descuenta por criterios incumplidos.
        ``points`` es el aporte ponderado al score global.
        """
        cats = [
            self._cat_profitability(kpis, thresholds),
            self._cat_liquidity(kpis, thresholds),
            self._cat_cashflow(kpis, thresholds),
            self._cat_collection(aging, thresholds),
            self._cat_leverage(kpis),
            self._cat_data_quality(data_quality),
        ]
        for c in cats:
            c['score'] = max(0, min(100, round(c['score'])))
            c['weight'] = CATEGORY_WEIGHTS[c['key']]
            c['points'] = round(c['score'] * c['weight'] / 100.0)
            c['label'] = _(CATEGORY_LABELS[c['key']])
        return cats

    # ---- 1) Rentabilidad ---------------------------------------------
    def _cat_profitability(self, kpis, thr):
        score = 100
        criteria = []
        revenue = kpis.get('revenue') or 0.0
        net_profit = kpis.get('net_profit') or 0.0
        net_margin = kpis.get('net_margin') or 0.0
        gross_margin = kpis.get('gross_margin') or 0.0
        expenses = kpis.get('expenses') or 0.0
        min_margin = thr.get('min_net_margin', 5.0)
        max_exp_ratio = thr.get('max_expense_ratio', 70.0)

        if net_profit > 0:
            criteria.append(self._ok(
                _('Utilidad neta positiva'),
                _('Resultado del período: %s') % self._money(net_profit), 10))
        elif net_profit < 0:
            score -= 40
            criteria.append(self._fail(
                _('Utilidad neta negativa'),
                _('Los gastos superan los ingresos (%s).') % self._money(net_profit),
                -40, severity='danger'))

        if revenue:
            if net_margin >= min_margin:
                criteria.append(self._ok(
                    _('Margen neto cumple objetivo'),
                    _('%.1f%% (objetivo ≥ %.1f%%)') % (net_margin, min_margin), 10))
            else:
                penalty = -20
                score += penalty
                criteria.append(self._fail(
                    _('Margen neto bajo'),
                    _('%.1f%% (objetivo ≥ %.1f%%).') % (net_margin, min_margin),
                    penalty, severity='warning'))

            exp_ratio = expenses / revenue * 100.0 if revenue else 0.0
            if exp_ratio > max_exp_ratio:
                penalty = -15
                score += penalty
                criteria.append(self._fail(
                    _('Gastos elevados'),
                    _('%.1f%% de los ingresos (límite %.0f%%).') % (exp_ratio, max_exp_ratio),
                    penalty, severity='warning'))

        if gross_margin and gross_margin < 20.0:
            penalty = -10
            score += penalty
            criteria.append(self._fail(
                _('Margen bruto bajo'),
                _('%.1f%% (referencia ≥ 20%%).') % gross_margin,
                penalty, severity='info'))

        return {'key': 'profitability', 'score': score, 'criteria': criteria}

    # ---- 2) Liquidez --------------------------------------------------
    def _cat_liquidity(self, kpis, thr):
        score = 100
        criteria = []
        cr = kpis.get('current_ratio') or 0.0
        qr = kpis.get('quick_ratio') or 0.0
        wc = kpis.get('working_capital') or 0.0
        min_cr = thr.get('min_current_ratio', 1.0)
        min_wc = thr.get('min_working_capital', 0.0)

        if cr >= min_cr:
            criteria.append(self._ok(
                _('Razón corriente saludable'),
                _('%.2f (objetivo ≥ %.2f)') % (cr, min_cr), 10))
        else:
            penalty = -30
            score += penalty
            criteria.append(self._fail(
                _('Razón corriente baja'),
                _('%.2f (objetivo ≥ %.2f).') % (cr, min_cr),
                penalty, severity='danger'))

        if qr >= 0.8:
            criteria.append(self._ok(
                _('Prueba ácida saludable'),
                _('%.2f (referencia ≥ 0.80)') % qr, 5))
        elif qr:
            penalty = -10
            score += penalty
            criteria.append(self._fail(
                _('Prueba ácida baja'),
                _('%.2f (referencia ≥ 0.80).') % qr,
                penalty, severity='warning'))

        if wc >= min_wc:
            criteria.append(self._ok(
                _('Capital de trabajo positivo'),
                self._money(wc), 10))
        else:
            penalty = -25
            score += penalty
            criteria.append(self._fail(
                _('Capital de trabajo bajo'),
                _('Posible presión de liquidez de corto plazo.'),
                penalty, severity='warning'))

        return {'key': 'liquidity', 'score': score, 'criteria': criteria}

    # ---- 3) Flujo de caja --------------------------------------------
    def _cat_cashflow(self, kpis, thr):
        score = 100
        criteria = []
        cash = kpis.get('cash_surplus') or 0.0
        closing = kpis.get('closing_bank') or 0.0
        min_cf = thr.get('min_cash_flow', 0.0)

        if cash >= min_cf and cash > 0:
            criteria.append(self._ok(
                _('Flujo de caja positivo'),
                self._money(cash), 15))
        elif cash >= min_cf:
            criteria.append(self._ok(
                _('Flujo de caja cumple objetivo'),
                self._money(cash), 10))
        else:
            penalty = -35
            score += penalty
            criteria.append(self._fail(
                _('Flujo de caja bajo'),
                _('Período: %s (mínimo %s).') % (self._money(cash), self._money(min_cf)),
                penalty, severity='warning'))

        if closing > 0:
            criteria.append(self._ok(
                _('Saldo bancario positivo'),
                self._money(closing), 5))
        elif closing < 0:
            penalty = -20
            score += penalty
            criteria.append(self._fail(
                _('Bancos en negativo'),
                self._money(closing),
                penalty, severity='danger'))

        return {'key': 'cashflow', 'score': score, 'criteria': criteria}

    # ---- 4) Cobranza --------------------------------------------------
    def _cat_collection(self, aging, thr):
        score = 100
        criteria = []
        rec = (aging or {}).get('receivable') or {}
        total = rec.get('total') or 0.0
        overdue = rec.get('overdue') or 0.0
        over120 = rec.get('over_120') or 0.0
        max_overdue = thr.get('max_overdue_receivable_pct', 30.0)
        max_over120 = thr.get('max_over_120_pct', 15.0)

        if not total:
            criteria.append(self._ok(
                _('Sin cartera vencida'),
                _('No hay saldos pendientes por cobrar.'), 5))
            return {'key': 'collection', 'score': score, 'criteria': criteria}

        overdue_pct = overdue / total * 100.0 if total else 0.0
        over120_pct = over120 / total * 100.0 if total else 0.0

        if overdue_pct <= max_overdue:
            criteria.append(self._ok(
                _('Cartera vencida bajo control'),
                _('%.1f%% (objetivo ≤ %.0f%%)') % (overdue_pct, max_overdue), 10))
        else:
            penalty = -25
            score += penalty
            criteria.append(self._fail(
                _('Cartera vencida elevada'),
                _('%.1f%% del total (límite %.0f%%).') % (overdue_pct, max_overdue),
                penalty, severity='warning',
                impact_amount=round(overdue, 2)))

        if over120_pct <= max_over120:
            criteria.append(self._ok(
                _('Cartera +120 días bajo control'),
                _('%.1f%% (objetivo ≤ %.0f%%)') % (over120_pct, max_over120), 5))
        else:
            penalty = -30
            score += penalty
            criteria.append(self._fail(
                _('Cartera +120 días crítica'),
                _('%.1f%% del total (límite %.0f%%).') % (over120_pct, max_over120),
                penalty, severity='danger',
                impact_amount=round(over120, 2)))

        return {'key': 'collection', 'score': score, 'criteria': criteria}

    # ---- 5) Endeudamiento --------------------------------------------
    def _cat_leverage(self, kpis):
        score = 100
        criteria = []
        assets = kpis.get('total_assets') or 0.0
        net_assets = kpis.get('net_assets') or 0.0
        payables = kpis.get('payables') or 0.0
        # liabilities (pasivos) = activos − patrimonio neto
        liabilities = max(0.0, assets - net_assets)
        debt_ratio = (liabilities / assets * 100.0) if assets else 0.0

        if assets <= 0:
            criteria.append(self._ok(
                _('Activos no disponibles'),
                _('Sin activos suficientes para evaluar.'), 0))
            return {'key': 'leverage', 'score': 50, 'criteria': criteria}

        if debt_ratio <= 40.0:
            criteria.append(self._ok(
                _('Endeudamiento bajo'),
                _('Pasivo/Activo: %.1f%% (≤ 40%%).') % debt_ratio, 15))
        elif debt_ratio <= 60.0:
            penalty = -10
            score += penalty
            criteria.append(self._fail(
                _('Endeudamiento moderado'),
                _('Pasivo/Activo: %.1f%% (40%% – 60%%).') % debt_ratio,
                penalty, severity='info'))
        elif debt_ratio <= 80.0:
            penalty = -25
            score += penalty
            criteria.append(self._fail(
                _('Endeudamiento alto'),
                _('Pasivo/Activo: %.1f%% (60%% – 80%%).') % debt_ratio,
                penalty, severity='warning'))
        else:
            penalty = -45
            score += penalty
            criteria.append(self._fail(
                _('Endeudamiento crítico'),
                _('Pasivo/Activo: %.1f%% (> 80%%).') % debt_ratio,
                penalty, severity='danger'))

        if payables > 0 and assets:
            pay_ratio = payables / assets * 100.0
            if pay_ratio > 30.0:
                penalty = -10
                score += penalty
                criteria.append(self._fail(
                    _('Cuentas por pagar elevadas'),
                    _('%.1f%% de los activos.') % pay_ratio,
                    penalty, severity='info'))

        return {'key': 'leverage', 'score': score, 'criteria': criteria}

    # ---- 6) Calidad de datos -----------------------------------------
    def _cat_data_quality(self, data_quality):
        score = 100
        criteria = []
        checks = (data_quality or {}).get('checks') or []
        if not checks:
            criteria.append(self._ok(
                _('Calidad contable óptima'),
                _('Sin incidencias detectadas.'), 10))
            return {'key': 'data_quality', 'score': score, 'criteria': criteria}
        # Penaliza por severidad y acumula los puntos descontados.
        for chk in checks:
            sev = chk.get('severity') or 'info'
            count = chk.get('count') or 0
            base = 10 if sev == 'warning' else 20 if sev == 'danger' else 5
            penalty = -min(base + count // 5, 30)
            score += penalty
            criteria.append(self._fail(
                chk.get('title') or _('Incidencia contable'),
                chk.get('message') or '',
                penalty, severity=sev))
        return {'key': 'data_quality', 'score': score, 'criteria': criteria}

    # ------------------------------------------------------------------
    # Score global / nivel / riesgo / radar
    # ------------------------------------------------------------------
    def _global_score(self, categories):
        total = sum(c['points'] for c in categories)
        score = max(0, min(100, int(round(total))))
        if score >= 80:
            return score, 'excellent', _('Excelente')
        if score >= 60:
            return score, 'good', _('Buena')
        if score >= 40:
            return score, 'warning', _('Atención')
        return score, 'risk', _('Riesgo')

    def _risk_indicator(self, score, categories):
        """Velocímetro 0-100 (5 estados). Castiga si liquidez o flujo están
        muy bajos aunque el global sea aceptable."""
        liq = next((c['score'] for c in categories if c['key'] == 'liquidity'), 100)
        cf = next((c['score'] for c in categories if c['key'] == 'cashflow'), 100)
        col = next((c['score'] for c in categories if c['key'] == 'collection'), 100)
        # Penaliza el global si alguna dimensión crítica está muy baja.
        critical = min(liq, cf, col)
        value = round(0.55 * score + 0.45 * critical)
        value = max(0, min(100, value))
        for threshold, key, label in RISK_LEVELS:
            if value >= threshold:
                return {'value': value, 'level': key, 'label': _(label)}
        return {'value': value, 'level': 'critical', 'label': _('Crítico')}

    def _radar(self, categories, kpis, trends):
        """8 ejes 0-100 con las categorías + Capital de trabajo y Crecimiento.

        - Capital de trabajo: 100 si > 0 (escalado por current_ratio).
        - Crecimiento: derivado de tendencias (subiendo = 100, plana 50, baja 0).
        """
        cat_score = {c['key']: c['score'] for c in categories}
        cr = kpis.get('current_ratio') or 0.0
        wc_score = 0
        if cr >= 2:
            wc_score = 100
        elif cr >= 1:
            wc_score = 60 + int((cr - 1) * 40)
        elif cr > 0:
            wc_score = int(cr * 60)
        growth_score = self._growth_score(trends)
        axes = [
            ('profitability', _('Rentabilidad')),
            ('liquidity', _('Liquidez')),
            ('cashflow', _('Flujo')),
            ('collection', _('Cobranza')),
            ('leverage', _('Endeudamiento')),
            ('data_quality', _('Calidad de datos')),
        ]
        labels = [lbl for _k, lbl in axes]
        values = [cat_score.get(k, 0) for k, _lbl in axes]
        labels.append(_('Capital de trabajo'))
        values.append(wc_score)
        labels.append(_('Crecimiento'))
        values.append(growth_score)
        return {'labels': labels, 'values': values}

    def _growth_score(self, trends):
        """Score 0-100 desde la dirección de revenue/net_profit/cash."""
        if not trends:
            return 50
        keys = ('revenue', 'net_profit', 'cash_surplus')
        ups = downs = flat = 0
        for k in keys:
            d = (trends.get(k) or {}).get('direction')
            if d == 'up':
                ups += 1
            elif d == 'down':
                downs += 1
            else:
                flat += 1
        if ups + downs == 0:
            return 50
        # Cada subiendo: +35, bajando: -25, plano: +5
        raw = 50 + ups * 30 - downs * 25 + flat * 2
        return max(0, min(100, raw))

    # ------------------------------------------------------------------
    # Recomendaciones / centro de decisiones
    # ------------------------------------------------------------------
    def _recommendations(self, categories, kpis, aging):
        """Genera recomendaciones desde los criterios incumplidos."""
        recs = []
        for cat in categories:
            for crit in cat['criteria']:
                if crit.get('met'):
                    continue
                action = self._action_for(cat['key'], crit, kpis, aging)
                if not action:
                    continue
                recs.append(action)
        recs.sort(key=lambda r: (
            {'high': 0, 'medium': 1, 'low': 2}.get(r['priority'], 1),
            -(r.get('impact_amount') or 0),
        ))
        return recs

    def _action_for(self, cat_key, crit, kpis, aging):
        """Mapea un criterio incumplido a una acción recomendada."""
        sev = crit.get('severity') or 'info'
        priority = {'danger': 'high', 'warning': 'medium', 'info': 'low'}.get(sev, 'low')
        impact = crit.get('impact_amount') or 0.0
        templates = {
            ('profitability', 'Margen neto bajo'): (
                _('Revisar precios y costos para mejorar el margen.'),
                _('Aumentar el margen neto al objetivo configurado.'),
                _('1-2 meses')),
            ('profitability', 'Utilidad neta negativa'): (
                _('Plan de reducción de gastos administrativos.'),
                _('Llevar la utilidad neta a positivo.'),
                _('1-3 meses')),
            ('profitability', 'Gastos elevados'): (
                _('Renegociar contratos con proveedores principales.'),
                _('Reducir la proporción de gastos sobre ingresos.'),
                _('1-2 meses')),
            ('liquidity', 'Razón corriente baja'): (
                _('Reforzar capital de trabajo con financiamiento corto.'),
                _('Asegurar cobertura del pasivo corriente.'),
                _('30 días')),
            ('liquidity', 'Capital de trabajo bajo'): (
                _('Acelerar la cobranza y diferir pagos no críticos.'),
                _('Restablecer capital de trabajo positivo.'),
                _('30-60 días')),
            ('cashflow', 'Flujo de caja bajo'): (
                _('Plan de cobranza intensiva y pausa en gastos no esenciales.'),
                _('Generar flujo de caja positivo.'),
                _('Inmediato')),
            ('cashflow', 'Bancos en negativo'): (
                _('Cubrir sobregiros con líneas de crédito o cobros.'),
                _('Estabilizar saldos bancarios positivos.'),
                _('Inmediato')),
            ('collection', 'Cartera vencida elevada'): (
                _('Gestión intensiva de cobro a clientes vencidos.'),
                _('Recuperación parcial de la cartera vencida.'),
                _('30-45 días')),
            ('collection', 'Cartera +120 días crítica'): (
                _('Reclamar cartera +120 días y revisar políticas de crédito.'),
                _('Reducir la cartera +120 días al objetivo.'),
                _('45-90 días')),
            ('leverage', 'Endeudamiento crítico'): (
                _('Plan de reestructuración financiera y reducción de deuda.'),
                _('Bajar la razón de endeudamiento.'),
                _('3-6 meses')),
            ('leverage', 'Endeudamiento alto'): (
                _('Priorizar pago de pasivos con mayor costo.'),
                _('Bajar la razón de endeudamiento al rango moderado.'),
                _('2-4 meses')),
            ('data_quality', 'Apuntes sin tercero'): (
                _('Completar el tercero en cuentas por cobrar/pagar.'),
                _('Asegurar trazabilidad de la cartera.'),
                _('Hoy')),
            ('data_quality', 'Asientos descuadrados'): (
                _('Revisar y reasentar los asientos descuadrados.'),
                _('Información contable consistente.'),
                _('Hoy')),
            ('data_quality', 'Sin fecha de vencimiento'): (
                _('Capturar fecha de vencimiento en apuntes pendientes.'),
                _('Permite el cálculo correcto de antigüedad.'),
                _('Esta semana')),
            ('data_quality', 'Bancos en negativo'): (
                _('Conciliar y depurar bancos en negativo.'),
                _('Conciliación bancaria correcta.'),
                _('Esta semana')),
        }
        title = crit.get('title')
        tpl = templates.get((cat_key, title))
        if not tpl:
            return None
        action, benefit, eta = tpl
        return {
            'category': cat_key,
            'title': action,
            'description': crit.get('message', ''),
            'priority': priority,
            'expected_impact': benefit,
            'impact_amount': round(impact, 2) if impact else 0.0,
            'eta': eta,
            'severity': sev,
        }

    def _decisions(self, recommendations):
        """Centro de decisiones: top 5 recomendaciones por prioridad e impacto."""
        return recommendations[:5]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ok(self, label, detail, points):
        return {
            'label': label,
            'detail': detail,
            'points': points,
            'met': True,
            'severity': 'ok',
        }

    def _fail(self, label, detail, points, severity='warning', impact_amount=None):
        c = {
            'label': label,
            'title': label,
            'detail': detail,
            'message': detail,
            'points': points,
            'met': False,
            'severity': severity,
        }
        if impact_amount is not None:
            c['impact_amount'] = impact_amount
        return c

    def _money(self, value):
        symbol = self.env.company.currency_id.symbol or ''
        return '%s %s' % (symbol, '{:,.2f}'.format(value or 0.0))

    def _flatten_alerts(self, categories):
        """Lista plana ``{severity, title, message}`` para compatibilidad
        con el formato anterior de ``health.alerts``."""
        alerts = []
        for cat in categories:
            for crit in cat['criteria']:
                if crit.get('met') or crit.get('severity') == 'ok':
                    continue
                alerts.append({
                    'severity': crit.get('severity', 'warning'),
                    'title': crit.get('title') or crit.get('label'),
                    'message': crit.get('message') or crit.get('detail') or '',
                    'category': cat['key'],
                })
        return alerts
