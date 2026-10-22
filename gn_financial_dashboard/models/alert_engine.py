# -*- coding: utf-8 -*-
"""Motor de Alertas + Centro de Decisiones + Asistente IA (V20 Fase 6).

Tres responsabilidades agrupadas porque comparten contexto (KPIs ya
calculados, forecast, score y comparaciones de benchmark):

1. ``_evaluate_alerts(filters)`` — corre todas las reglas activas y
   añade señales derivadas (variaciones, predicciones negativas,
   concentración, objetivos en rojo) en una única lista.

2. ``get_decisions_data(filters)`` — sintetiza las alertas + insights de
   inteligencia de entidades en un top-N de "decisiones recomendadas"
   con acción concreta, impacto estimado y drill-down.

3. ``ask_ai(question, filters)`` — clasificador de intent simple (sin
   dependencias externas) + plantillas con datos reales. Hook
   ``_ai_call_llm`` para integrar un proveedor externo si la compañía
   lo configura (opt-in).
"""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------
SEVERITY_ORDER = {'critical': 3, 'warning': 2, 'info': 1}
DEFAULT_TOP_DECISIONS = 8

# Reglas "virtuales" siempre evaluadas (no se borran ni se editan, las
# añade el motor independientemente de las reglas configurables).
VIRTUAL_CHECKS = [
    'predictive_score_low',
    'cash_forecast_negative',
    'revenue_drop_yoy',
    'customer_concentration',
    'supplier_concentration',
    'goals_off_track',
]


class GnFinancialDashboardAlertEngine(models.AbstractModel):
    _inherit = 'gn.financial.dashboard'

    # ------------------------------------------------------------------
    # KPIs adicionales para alertas (no presentes en _kpis_for_period)
    # ------------------------------------------------------------------
    @api.model
    def _alert_extra_kpis(self, parsed, kpis_norm):
        """Calcula KPIs auxiliares solo usados por el motor de alertas."""
        out = {}
        # Mora % desde aging (si existe el cómputo). Reutilizamos lógica
        # simple: receivables / (receivables + payables) no aplica;
        # mejor leemos AML vencidos vs total.
        company = parsed['company']
        AML = self.env['account.move.line'].sudo()
        today = fields.Date.context_today(self)
        rec_types = ('asset_receivable',)
        type_map = self._account_type_map(company)
        rec_ids = [aid for aid, t in type_map.items() if t in rec_types]
        if rec_ids:
            domain = [
                ('account_id', 'in', rec_ids),
                ('parent_state', '=', 'posted'),
                ('company_id', '=', company.id),
                ('amount_residual', '>', 0),
            ]
            total = sum(AML.search(domain).mapped('amount_residual'))
            overdue = sum(AML.search(domain + [('date_maturity', '<', today)])
                          .mapped('amount_residual'))
            out['overdue_pct'] = round((overdue / total * 100.0) if total else 0.0, 1)
        return out

    # ------------------------------------------------------------------
    # Motor principal: evaluación de alertas
    # ------------------------------------------------------------------
    @api.model
    def _evaluate_alerts(self, filters):
        """Devuelve la lista de alertas activas para el periodo filtrado.

        No persiste. Para persistir y reabrir/cerrar, llamar
        :meth:`sync_alert_events`.
        """
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        raw_kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        kpis = self._normalize_kpis(raw_kpis)
        # KPIs auxiliares (mora, concentración).
        kpis.update(self._alert_extra_kpis(parsed, kpis))

        # Reglas configurables.
        Rule = self.env['gn.financial.dashboard.alert.rule'].sudo()
        rules = Rule.search([
            ('company_id', 'in', [False, company.id]),
            ('active', '=', True),
        ])
        items = []
        for r in rules:
            value = kpis.get(r.kpi)
            if value is None:
                continue
            if not r.evaluate(value):
                continue
            items.append(self._mk_alert_item(
                code=r.code,
                name=r.name,
                severity=r.severity,
                category=r.category,
                message=r.render_message(value, company),
                action_hint=r.action_hint,
                kpi_value=value,
                threshold=r.threshold,
                rule_id=r.id,
                source='rule',
                payload={'kpi': r.kpi, 'op': r.operator},
                decision_priority=r.decision_priority,
            ))

        # Concentración de cliente/proveedor desde Intelligence.
        items += self._alerts_from_concentration(parsed, kpis, company)
        # Objetivos en riesgo.
        items += self._alerts_from_goals(parsed, company)
        # Score predictivo bajo + flujo de caja proyectado negativo.
        items += self._alerts_from_predictive(parsed, company, kpis)

        # De-duplicación por code: si una regla "manual" cubre el mismo
        # code que una virtual, la regla manual gana (más específica).
        dedup = {}
        for it in items:
            key = it['code'] or (it['source'] + ':' + it['name'][:40])
            cur = dedup.get(key)
            if not cur or SEVERITY_ORDER.get(it['severity'], 0) > SEVERITY_ORDER.get(cur['severity'], 0):
                dedup[key] = it
        result = list(dedup.values())
        # Orden por severidad descendente y prioridad de decisión.
        result.sort(key=lambda x: (SEVERITY_ORDER.get(x['severity'], 0),
                                    x.get('decision_priority', 50)),
                    reverse=True)
        return {
            'alerts': result,
            'by_severity': self._count_by(result, 'severity'),
            'by_category': self._count_by(result, 'category'),
            'kpis': kpis,
        }

    @api.model
    def _mk_alert_item(self, code, name, severity, category, message,
                       action_hint=None, kpi_value=None, threshold=None,
                       rule_id=None, source='rule', payload=None,
                       decision_priority=50):
        return {
            'code': code,
            'name': name,
            'severity': severity,
            'category': category,
            'message': message,
            'action_hint': action_hint or '',
            'kpi_value': kpi_value,
            'threshold': threshold,
            'rule_id': rule_id,
            'source': source,
            'payload': payload or {},
            'decision_priority': decision_priority,
        }

    @api.model
    def _count_by(self, items, key):
        out = defaultdict(int)
        for it in items:
            out[it.get(key) or 'other'] += 1
        return dict(out)

    # ------------------------------------------------------------------
    # Señales virtuales (siempre evaluadas)
    # ------------------------------------------------------------------
    @api.model
    def _alerts_from_concentration(self, parsed, kpis, company):
        out = []
        # Reutilizamos la inteligencia de entidades si está disponible.
        try:
            cust = self.get_customer_intelligence({
                'company_id': company.id,
                'date_from': parsed['date_from'].isoformat(),
                'date_to': parsed['date_to'].isoformat(),
                'target_move': parsed['target_move'],
                'comparison': parsed.get('comparison', 'none'),
            })
        except Exception:
            cust = None
        if cust and cust.get('items'):
            total = cust.get('total_revenue') or sum(c.get('revenue', 0) for c in cust['items'])
            top1 = cust['items'][0]
            if total > 0:
                pct = round(top1.get('revenue', 0) / total * 100.0, 1)
                if pct >= 30:
                    sev = 'critical' if pct >= 50 else 'warning'
                    out.append(self._mk_alert_item(
                        code='customer_concentration',
                        name=_('Alta concentración en cliente top'),
                        severity=sev,
                        category='risk',
                        message=_(
                            'El cliente "%(name)s" representa el %(pct)s%% '
                            'de los ingresos del periodo.'
                        ) % {'name': top1['name'], 'pct': pct},
                        action_hint=_(
                            'Diversifica la cartera de clientes para reducir '
                            'el riesgo de dependencia.'
                        ),
                        kpi_value=pct, threshold=30,
                        source='virtual',
                        payload={'partner_id': top1.get('partner_id')},
                        decision_priority=80 if sev == 'critical' else 60,
                    ))

        try:
            sup = self.get_supplier_intelligence({
                'company_id': company.id,
                'date_from': parsed['date_from'].isoformat(),
                'date_to': parsed['date_to'].isoformat(),
                'target_move': parsed['target_move'],
                'comparison': parsed.get('comparison', 'none'),
            })
        except Exception:
            sup = None
        if sup and sup.get('items'):
            total = sup.get('total_purchases') or sum(s.get('purchases', 0) for s in sup['items'])
            top1 = sup['items'][0]
            if total > 0:
                pct = round(top1.get('purchases', 0) / total * 100.0, 1)
                if pct >= 40:
                    sev = 'critical' if pct >= 60 else 'warning'
                    out.append(self._mk_alert_item(
                        code='supplier_concentration',
                        name=_('Dependencia alta de un proveedor'),
                        severity=sev,
                        category='risk',
                        message=_(
                            'El proveedor "%(name)s" concentra el %(pct)s%% '
                            'de las compras.'
                        ) % {'name': top1['name'], 'pct': pct},
                        action_hint=_('Identifica proveedores alternativos.'),
                        kpi_value=pct, threshold=40,
                        source='virtual',
                        payload={'partner_id': top1.get('partner_id')},
                        decision_priority=70 if sev == 'critical' else 55,
                    ))
        return out

    @api.model
    def _alerts_from_goals(self, parsed, company):
        out = []
        try:
            payload = self.get_goals_progress({
                'company_id': company.id,
                'date_from': parsed['date_from'].isoformat(),
                'date_to': parsed['date_to'].isoformat(),
                'target_move': parsed['target_move'],
                'comparison': parsed.get('comparison', 'none'),
            })
        except Exception:
            return out
        for g in (payload or {}).get('goals', []):
            status = g.get('status')
            if status in ('off_track', 'critical', 'red'):
                sev = 'critical' if status == 'critical' or status == 'red' else 'warning'
                out.append(self._mk_alert_item(
                    code='goal_%s' % g.get('id'),
                    name=_('Objetivo en riesgo: %s') % g.get('name'),
                    severity=sev,
                    category='growth',
                    message=_(
                        'El objetivo "%(name)s" tiene progreso %(pct)s%% '
                        '(meta %(target)s).'
                    ) % {
                        'name': g.get('name'),
                        'pct': g.get('progress_pct'),
                        'target': g.get('target'),
                    },
                    action_hint=_('Revisa el plan de acción o ajusta la meta.'),
                    kpi_value=g.get('progress_pct'),
                    threshold=100,
                    source='virtual',
                    payload={'goal_id': g.get('id')},
                    decision_priority=65,
                ))
        return out

    @api.model
    def _alerts_from_predictive(self, parsed, company, kpis):
        out = []
        try:
            pred = self.get_predictions_data({
                'company_id': company.id,
                'date_from': parsed['date_from'].isoformat(),
                'date_to': parsed['date_to'].isoformat(),
                'target_move': parsed['target_move'],
                'comparison': parsed.get('comparison', 'none'),
                'forecast_horizon': 6,
                'history_months': 18,
            })
        except Exception:
            return out
        score = (pred.get('score') or {}).get('score')
        if score is not None and score < 50:
            out.append(self._mk_alert_item(
                code='predictive_score_low',
                name=_('Score predictivo bajo'),
                severity='critical' if score < 35 else 'warning',
                category='risk',
                message=_('El score predictivo del negocio es %s/100.') % score,
                action_hint=_('Revisa las recomendaciones en la pestaña Predicciones.'),
                kpi_value=score, threshold=50,
                source='virtual',
                payload={'tier': (pred.get('score') or {}).get('tier')},
                decision_priority=90 if score < 35 else 70,
            ))
        cash = (pred.get('forecast') or {}).get('cash_flow') or {}
        forecast = cash.get('forecast') or []
        n_neg = sum(1 for v in forecast if v < 0)
        if forecast and n_neg >= max(2, len(forecast) // 2):
            out.append(self._mk_alert_item(
                code='cash_forecast_negative',
                name=_('Flujo de caja proyectado en rojo'),
                severity='critical' if n_neg == len(forecast) else 'warning',
                category='liquidity',
                message=_(
                    '%(neg)d de los próximos %(n)d meses proyectan flujo '
                    'de caja negativo.'
                ) % {'neg': n_neg, 'n': len(forecast)},
                action_hint=_('Acelera cobros, retrasa pagos o consigue financiamiento.'),
                kpi_value=n_neg, threshold=len(forecast) // 2,
                source='virtual',
                payload={'forecast': forecast},
                decision_priority=85,
            ))
        return out

    # ------------------------------------------------------------------
    # Persistencia (sync)
    # ------------------------------------------------------------------
    @api.model
    def sync_alert_events(self, filters):
        """Genera/cierra eventos persistentes a partir de alertas vivas.

        Reglas:
        - Si una alerta vive en el motor y no hay evento ``open`` con
          mismo ``code+company``: se crea uno nuevo.
        - Si la alerta dejó de dispararse y hay un evento ``open``: se
          marca ``resolved`` automáticamente.
        - Eventos ``ack`` o ``snoozed`` se respetan; no se reabren ni se
          cierran solos.
        """
        data = self._evaluate_alerts(filters)
        company = self.env['res.company'].browse(filters.get('company_id') or self.env.company.id)
        Event = self.env['gn.financial.dashboard.alert.event'].sudo()
        alive_codes = {a['code'] for a in data['alerts'] if a.get('code')}
        open_events = Event.search([
            ('company_id', '=', company.id), ('state', '=', 'open'),
            ('code', '!=', False),
        ])
        existing_by_code = {ev.code: ev for ev in open_events}
        # Crear nuevos eventos.
        for a in data['alerts']:
            code = a.get('code')
            if not code or code in existing_by_code:
                continue
            Event.create({
                'name': a['name'],
                'rule_id': a.get('rule_id') or False,
                'code': code,
                'company_id': company.id,
                'severity': a['severity'],
                'category': a['category'],
                'kpi_value': a.get('kpi_value') or 0.0,
                'threshold': a.get('threshold') or 0.0,
                'action_hint': a.get('action_hint') or '',
                'payload': json.dumps(a.get('payload') or {}),
            })
        # Auto-resolver eventos cuyas alertas dejaron de dispararse.
        for code, ev in existing_by_code.items():
            if code not in alive_codes:
                ev.action_resolve(note=_('Resolución automática: condición ya no aplica.'))
        return {'created': len(alive_codes - set(existing_by_code)),
                'resolved_auto': len(set(existing_by_code) - alive_codes)}

    @api.model
    def get_alerts_data(self, filters):
        """Devuelve alertas vivas + eventos persistentes recientes."""
        live = self._evaluate_alerts(filters)
        Event = self.env['gn.financial.dashboard.alert.event'].sudo()
        company_id = filters.get('company_id') or self.env.company.id
        recent = Event.search_read(
            [('company_id', '=', company_id)],
            ['name', 'severity', 'category', 'state', 'date',
             'date_ack', 'date_resolved', 'snoozed_until',
             'kpi_value', 'threshold', 'action_hint', 'note',
             'user_ack_id', 'user_resolved_id', 'code', 'rule_id'],
            order='date desc', limit=50,
        )
        return {
            'live_alerts': live['alerts'],
            'recent_events': recent,
            'by_severity': live['by_severity'],
            'by_category': live['by_category'],
        }

    @api.model
    def acknowledge_alert_event(self, event_id, note=None):
        ev = self.env['gn.financial.dashboard.alert.event'].sudo().browse(event_id)
        if ev.exists():
            ev.action_acknowledge(note=note)
        return True

    @api.model
    def resolve_alert_event(self, event_id, note=None):
        ev = self.env['gn.financial.dashboard.alert.event'].sudo().browse(event_id)
        if ev.exists():
            ev.action_resolve(note=note)
        return True

    @api.model
    def snooze_alert_event(self, event_id, hours):
        ev = self.env['gn.financial.dashboard.alert.event'].sudo().browse(event_id)
        if ev.exists():
            until = fields.Datetime.now() + timedelta(hours=int(hours or 24))
            ev.action_snooze(until)
        return True

    # ------------------------------------------------------------------
    # Centro de decisiones (#22)
    # ------------------------------------------------------------------
    @api.model
    def get_decisions_data(self, filters):
        """Lista priorizada de decisiones recomendadas (top N).

        Combina alertas + inteligencia de entidades + score predictivo
        en decisiones accionables, cada una con:
          - title, summary, action_hint
          - urgency (1-5), impact_pct (estimado o None), category
          - drilldown (acción opcional para enviar al usuario al detalle)
        """
        parsed = self._parse_filters(filters)
        company = parsed['company']
        live = self._evaluate_alerts(filters)
        decisions = []
        for a in live['alerts']:
            urgency = {'critical': 5, 'warning': 3, 'info': 2}.get(a['severity'], 2)
            decisions.append({
                'kind': 'alert',
                'title': a['name'],
                'summary': a['message'],
                'action_hint': a['action_hint'],
                'urgency': urgency,
                'category': a['category'],
                'priority': a.get('decision_priority', 50) + urgency * 10,
                'drilldown': a.get('payload') or {},
                'source_code': a.get('code'),
            })

        # Insights desde inteligencia de productos (margen negativo).
        try:
            prods = self.get_product_intelligence({
                'company_id': company.id,
                'date_from': parsed['date_from'].isoformat(),
                'date_to': parsed['date_to'].isoformat(),
                'target_move': parsed['target_move'],
                'comparison': parsed.get('comparison', 'none'),
            })
            for p in (prods.get('loss_items') or [])[:3]:
                decisions.append({
                    'kind': 'opportunity',
                    'title': _('Producto con pérdidas: %s') % p.get('name', '—'),
                    'summary': _('Ingreso %(rev)s, COGS %(cogs)s, margen %(m).1f%%.') % {
                        'rev': self._ai_num(p.get('revenue'), 0),
                        'cogs': self._ai_num(p.get('cogs'), 0),
                        'm': p.get('margin_pct') or 0.0,
                    },
                    'action_hint': _(
                        'Revisa precio de venta, costo unitario o si conviene '
                        'discontinuar.'
                    ),
                    'urgency': 4,
                    'category': 'profitability',
                    'priority': 75,
                    'drilldown': {'product_id': p.get('product_id')},
                })
        except Exception:
            pass

        # Insights de clientes en riesgo (tier critical/risky con alta mora).
        try:
            cust = self.get_customer_intelligence({
                'company_id': company.id,
                'date_from': parsed['date_from'].isoformat(),
                'date_to': parsed['date_to'].isoformat(),
                'target_move': parsed['target_move'],
                'comparison': parsed.get('comparison', 'none'),
            })
            for c in (cust.get('alerts') or [])[:3]:
                decisions.append({
                    'kind': 'alert',
                    'title': _('Cliente en riesgo: %s') % c['name'],
                    'summary': c.get('reason') or _('Score bajo y/o alta mora.'),
                    'action_hint': _(
                        'Llama al cliente, ajusta crédito o gestiona cobranza.'
                    ),
                    'urgency': 4,
                    'category': 'risk',
                    'priority': 70,
                    'drilldown': {'partner_id': c.get('partner_id')},
                })
        except Exception:
            pass

        # Ordenar por prioridad descendente; cap al top-N.
        decisions.sort(key=lambda d: d['priority'], reverse=True)
        top = int(filters.get('decisions_top') or DEFAULT_TOP_DECISIONS)
        return {
            'decisions': decisions[:top],
            'total': len(decisions),
        }

    # ------------------------------------------------------------------
    # Asistente IA financiero (#23)
    # ------------------------------------------------------------------
    @api.model
    def ask_ai(self, question, filters=None):
        """Responde una pregunta en lenguaje natural con datos del tablero.

        Estrategia:
        1. Normaliza la pregunta (lowercase, sin acentos).
        2. Aplica un clasificador de intents basado en keywords.
        3. Construye una respuesta combinando texto narrativo + datos
           reales (KPIs, alertas, top entidades).

        El método admite override en módulos descendentes que quieran
        integrar un LLM externo (OpenAI, Claude, Ollama, etc.):
        sobreescribe ``_ai_call_llm`` y devuelve un dict con clave
        ``answer`` para que reemplace la respuesta nativa.
        """
        filters = filters or {}
        q = (question or '').strip()
        if not q:
            return {
                'answer': _('Por favor escribe una pregunta.'),
                'intent': 'noop', 'data': {},
            }

        # Hook para LLM externo: si está configurado, lo usamos.
        llm = self._ai_call_llm(q, filters)
        if llm and llm.get('answer'):
            return {**llm, 'intent': llm.get('intent', 'llm'), 'data': llm.get('data', {})}

        intent = self._ai_classify_intent(q)
        try:
            handler = getattr(self, '_ai_handle_%s' % intent)
        except Exception:
            handler = self._ai_handle_overview
        try:
            return handler(q, filters)
        except Exception as e:
            return {
                'answer': _('No pude calcular esa respuesta: %s') % str(e),
                'intent': intent, 'data': {},
            }

    @api.model
    def _ai_call_llm(self, question, filters):
        """Hook opcional para LLM externo vía parámetros del sistema.

        Activar con ``ir.config_parameter``:
        - ``gn_fd.ai_llm_enabled`` = ``True``
        - ``gn_fd.ai_llm_url`` = endpoint HTTP POST (JSON)
        - ``gn_fd.ai_llm_api_key`` = token Bearer opcional

        El endpoint debe responder ``{"answer": "...", "intent": "...", "data": {}}``.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('gn_fd.ai_llm_enabled', 'False') != 'True':
            return None
        url = (ICP.get_param('gn_fd.ai_llm_url') or '').strip()
        if not url:
            return None
        try:
            import json
            import urllib.error
            import urllib.request

            payload = json.dumps({
                'question': question,
                'filters': filters or {},
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, method='POST')
            req.add_header('Content-Type', 'application/json')
            api_key = (ICP.get_param('gn_fd.ai_llm_api_key') or '').strip()
            if api_key:
                req.add_header('Authorization', 'Bearer %s' % api_key)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            answer = data.get('answer') or data.get('response')
            if not answer:
                return None
            return {
                'answer': answer,
                'intent': data.get('intent', 'llm'),
                'data': data.get('data') or {},
            }
        except Exception:
            _logger.warning('LLM hook failed for gn_financial_dashboard', exc_info=True)
        return None

    @api.model
    def _ai_classify_intent(self, q):
        """Clasificador muy simple basado en keywords."""
        ql = self._ai_normalize(q)
        rules = [
            ('alerts', ['alerta', 'urgente', 'rojo', 'critico', 'que esta mal', 'problema']),
            ('forecast', ['pronostico', 'proyeccion', 'predic', 'proximo mes', 'futuro', 'tendencia']),
            ('score', ['salud', 'score', 'puntaje', 'que tal va', 'como estamos']),
            ('cash', ['caja', 'efectivo', 'liquidez', 'banco', 'cash']),
            ('profit', ['utilidad', 'ganancia', 'profit', 'margen']),
            ('sales', ['venta', 'ingreso', 'facturacion']),
            ('customers', ['cliente', 'cartera', 'cxc', 'mora', 'cobr']),
            ('suppliers', ['proveedor', 'cxp', 'pago a proveed']),
            ('products', ['producto', 'sku', 'articulo']),
            ('benchmark', ['benchmark', 'sector', 'comparar', 'industria']),
            ('decisions', ['que hacer', 'que debo', 'recomend', 'decision', 'siguiente paso', 'prioridad']),
            ('overview', ['resumen', 'general', 'overview', 'panorama']),
        ]
        for intent, kws in rules:
            for k in kws:
                if k in ql:
                    return intent
        return 'overview'

    @api.model
    def _ai_normalize(self, s):
        s = (s or '').lower()
        # Quita acentos básicos.
        repl = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
        for k, v in repl.items():
            s = s.replace(k, v)
        return re.sub(r'\s+', ' ', s).strip()

    # --- Handlers de intents ---
    @api.model
    def _ai_get_context(self, filters):
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        raw = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        kpis = self._normalize_kpis(raw)
        return parsed, kpis, self._currency_payload(company.currency_id)

    @api.model
    def _ai_money(self, value, cur):
        sym = (cur or {}).get('symbol') or ''
        try:
            return '%s%s' % (sym, '{:,.2f}'.format(float(value or 0.0)))
        except Exception:
            return str(value)

    @api.model
    def _ai_num(self, value, decimals=0):
        """Número con coma como separador de miles, punto decimal."""
        try:
            return ('{:,.%df}' % decimals).format(float(value or 0.0))
        except Exception:
            return str(value)

    @api.model
    def _ai_handle_overview(self, q, filters):
        parsed, k, cur = self._ai_get_context(filters)
        ans = _(
            'Resumen del periodo %(df)s — %(dt)s:\n'
            '• Ingresos: %(rev)s\n'
            '• Utilidad bruta: %(gp)s (margen %(gm).1f%%)\n'
            '• Utilidad neta: %(np)s (margen %(nm).1f%%)\n'
            '• Caja al cierre: %(cash)s\n'
            '• Razón corriente: %(cr).2f'
        ) % {
            'df': parsed['date_from'].strftime('%d/%m/%Y'),
            'dt': parsed['date_to'].strftime('%d/%m/%Y'),
            'rev': self._ai_money(k.get('revenue'), cur),
            'gp': self._ai_money(k.get('gross_profit'), cur),
            'gm': k.get('gross_margin_pct') or 0,
            'np': self._ai_money(k.get('net_profit'), cur),
            'nm': k.get('net_margin_pct') or 0,
            'cash': self._ai_money(k.get('closing_bank'), cur),
            'cr': k.get('current_ratio') or 0,
        }
        return {'answer': ans, 'intent': 'overview', 'data': {'kpis': {
            'revenue': k.get('revenue'), 'net_profit': k.get('net_profit'),
            'gross_margin_pct': k.get('gross_margin_pct'),
            'closing_bank': k.get('closing_bank'),
        }}}

    @api.model
    def _ai_handle_alerts(self, q, filters):
        live = self._evaluate_alerts(filters)
        if not live['alerts']:
            return {'answer': _('No hay alertas activas en este periodo. ¡Buen trabajo!'),
                    'intent': 'alerts', 'data': {}}
        bullets = []
        for a in live['alerts'][:5]:
            bullets.append('• [%s] %s — %s' % (
                a['severity'].upper(), a['name'], a['message']))
        ans = _('Hay %(n)d alertas activas. Las más importantes:\n%(b)s') % {
            'n': len(live['alerts']), 'b': '\n'.join(bullets)}
        return {'answer': ans, 'intent': 'alerts', 'data': {'alerts': live['alerts'][:10]}}

    @api.model
    def _ai_handle_forecast(self, q, filters):
        pred = self.get_predictions_data({**filters, 'forecast_horizon': 6, 'history_months': 18})
        rev = (pred.get('forecast') or {}).get('revenue') or {}
        cash = (pred.get('forecast') or {}).get('cash_flow') or {}
        rev_avg = sum(rev.get('forecast', [])) / max(len(rev.get('forecast', [])), 1)
        n_neg = sum(1 for v in cash.get('forecast', []) if v < 0)
        ans = _(
            'Pronóstico para los próximos %(h)d meses:\n'
            '• Ingresos promedio mensual proyectado: %(rev)s\n'
            '• Pendiente esperada: %(slope)s por mes\n'
            '• Flujo de caja negativo en %(neg)d de %(h)d meses proyectados'
        ) % {
            'h': len(rev.get('forecast', [])) or 6,
            'rev': self._ai_num(rev_avg, 0),
            'slope': self._ai_num((rev.get('forecast_meta') or {}).get('slope') or 0, 0),
            'neg': n_neg,
        }
        return {'answer': ans, 'intent': 'forecast', 'data': {'revenue_forecast': rev, 'cash_forecast': cash}}

    @api.model
    def _ai_handle_score(self, q, filters):
        pred = self.get_predictions_data(filters)
        sc = pred.get('score') or {}
        ans = _(
            'El score predictivo es %(s)s/100 (%(label)s).\n'
            '%(n)s'
        ) % {
            's': sc.get('score'), 'label': sc.get('label'),
            'n': '\n'.join('• ' + b for b in (sc.get('narrative') or [])[:3]),
        }
        return {'answer': ans, 'intent': 'score', 'data': sc}

    @api.model
    def _ai_handle_cash(self, q, filters):
        parsed, k, cur = self._ai_get_context(filters)
        ans = _(
            'Caja al cierre: %(cash)s\n'
            'Razón corriente: %(cr).2f\n'
            'Capital de trabajo: %(wc)s\n'
            'Días de cartera (DSO): %(dso)s\n'
            'Días de pago (DPO): %(dpo)s'
        ) % {
            'cash': self._ai_money(k.get('closing_bank'), cur),
            'cr': k.get('current_ratio') or 0,
            'wc': self._ai_money(k.get('working_capital'), cur),
            'dso': k.get('dso_days') or '—',
            'dpo': k.get('dpo_days') or '—',
        }
        return {'answer': ans, 'intent': 'cash', 'data': k}

    @api.model
    def _ai_handle_profit(self, q, filters):
        parsed, k, cur = self._ai_get_context(filters)
        ans = _(
            'Rentabilidad del periodo:\n'
            '• Utilidad bruta: %(gp)s (margen %(gm).1f%%)\n'
            '• Utilidad operativa: margen %(om).1f%%\n'
            '• EBITDA: margen %(em).1f%%\n'
            '• Utilidad neta: %(np)s (margen %(nm).1f%%)'
        ) % {
            'gp': self._ai_money(k.get('gross_profit'), cur),
            'gm': k.get('gross_margin_pct') or 0,
            'om': k.get('operating_margin_pct') or 0,
            'em': k.get('ebitda_margin_pct') or 0,
            'np': self._ai_money(k.get('net_profit'), cur),
            'nm': k.get('net_margin_pct') or 0,
        }
        return {'answer': ans, 'intent': 'profit', 'data': k}

    @api.model
    def _ai_handle_sales(self, q, filters):
        try:
            s = self.get_sales_data(filters)
            if not s.get('available'):
                raise Exception('no_sales_module')
            ans = _(
                'Ventas confirmadas: %(amt)s en %(n)d órdenes.\n'
                'Pipeline: %(pa)s en %(pn)d cotizaciones.\n'
                'Ticket promedio: %(avg)s.\n'
                'Conversión: %(c).1f%%.'
            ) % {
                'amt': self._ai_num(s['kpis']['confirmed_amount'], 0),
                'n': s['kpis']['confirmed_count'],
                'pa': self._ai_num(s['kpis']['pipeline_amount'], 0),
                'pn': s['kpis']['pipeline_count'],
                'avg': self._ai_num(s['kpis']['avg_ticket'], 0),
                'c': s['kpis']['conversion_pct'],
            }
            return {'answer': ans, 'intent': 'sales', 'data': s['kpis']}
        except Exception:
            # fallback a ingresos del P&L
            return self._ai_handle_overview(q, filters)

    @api.model
    def _ai_handle_customers(self, q, filters):
        try:
            cust = self.get_customer_intelligence(filters)
        except Exception:
            cust = {}
        if cust.get('items'):
            top1 = cust['items'][0]
            conc = (cust.get('concentration') or {}).get('top5_pct') or 0
            ans = _(
                'Cliente top: %(n)s con ingresos %(r)s.\n'
                'Concentración top-5: %(c).1f%%.\n'
                'Hay %(rk)d clientes en tier "risky" o "critical".'
            ) % {
                'n': top1.get('name', '—'),
                'r': self._ai_num(top1.get('revenue', 0), 0),
                'c': conc,
                'rk': sum(cust.get('tier_summary', {}).get(t, 0) for t in ('risky', 'critical')),
            }
            return {'answer': ans, 'intent': 'customers', 'data': cust}
        return {'answer': _('No hay datos suficientes de clientes en este periodo.'),
                'intent': 'customers', 'data': {}}

    @api.model
    def _ai_handle_suppliers(self, q, filters):
        try:
            sup = self.get_supplier_intelligence(filters)
        except Exception:
            sup = {}
        if sup.get('items'):
            top1 = sup['items'][0]
            conc = (sup.get('concentration') or {}).get('top5_pct') or 0
            ans = _(
                'Proveedor principal: %(n)s con compras %(p)s.\n'
                'Concentración top-5: %(c).1f%%.'
            ) % {
                'n': top1.get('name', '—'),
                'p': self._ai_num(top1.get('purchases', 0), 0),
                'c': conc,
            }
            return {'answer': ans, 'intent': 'suppliers', 'data': sup}
        return {'answer': _('No hay datos suficientes de proveedores.'),
                'intent': 'suppliers', 'data': {}}

    @api.model
    def _ai_handle_products(self, q, filters):
        try:
            prods = self.get_product_intelligence(filters)
        except Exception:
            prods = {}
        if prods.get('items'):
            top1 = prods['items'][0]
            losses = len(prods.get('loss_items') or [])
            ans = _(
                'Producto top por ingresos: %(n)s con %(r)s.\n'
                'Hay %(l)d productos con margen negativo.'
            ) % {'n': top1.get('name', '—'),
                 'r': self._ai_num(top1.get('revenue', 0), 0),
                 'l': losses}
            return {'answer': ans, 'intent': 'products', 'data': prods}
        return {'answer': _('No hay datos suficientes de productos.'),
                'intent': 'products', 'data': {}}

    @api.model
    def _ai_handle_benchmark(self, q, filters):
        try:
            bench = self.get_benchmark_data(filters)
        except Exception:
            bench = {}
        comps = bench.get('comparisons') or []
        if not comps:
            return {'answer': _('No hay benchmarks configurados.'),
                    'intent': 'benchmark', 'data': {}}
        good = sum(1 for c in comps if c['status'] == 'good')
        warn = sum(1 for c in comps if c['status'] == 'warn')
        bad = sum(1 for c in comps if c['status'] == 'bad')
        ans = _(
            'Comparativa contra el sector "%(s)s":\n'
            '• %(g)d KPIs cumpliendo, %(w)d por debajo, %(b)d en riesgo.'
        ) % {'s': bench.get('sector'), 'g': good, 'w': warn, 'b': bad}
        return {'answer': ans, 'intent': 'benchmark', 'data': bench}

    @api.model
    def _ai_handle_decisions(self, q, filters):
        d = self.get_decisions_data(filters)
        decs = d.get('decisions', [])
        if not decs:
            return {'answer': _('No hay decisiones recomendadas en este momento.'),
                    'intent': 'decisions', 'data': {}}
        bullets = []
        for i, dec in enumerate(decs[:5], 1):
            bullets.append('%d. %s — %s' % (i, dec['title'], dec.get('action_hint') or ''))
        ans = _('Top decisiones recomendadas:\n%s') % '\n'.join(bullets)
        return {'answer': ans, 'intent': 'decisions', 'data': decs[:10]}
