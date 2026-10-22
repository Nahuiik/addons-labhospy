# -*- coding: utf-8 -*-
"""Indicadores financieros (gauges/medidores).

Expone ``get_indicators_data`` que devuelve un conjunto de indicadores
clave del negocio, listos para ser presentados como medidores
semicirculares con tres zonas (mal / regular / bien) y una
interpretación corta. Reutiliza los KPIs ya calculados en
``_kpis_for_period`` y los indicadores de cobro/pago.

Cada indicador devuelve:
    - ``key``: identificador estable
    - ``name``: nombre legible
    - ``formula``: fórmula en lenguaje natural
    - ``value``: valor numérico actual
    - ``display``: valor formateado para mostrar
    - ``unit``: 'pct' | 'ratio' | 'days' | 'money' | 'times'
    - ``min`` / ``max``: rango del gauge
    - ``zones``: lista de tuplas (limit, color) que describen las
      bandas del gauge en orden ascendente
    - ``direction``: 'higher_better' | 'lower_better'
    - ``ok``, ``warn``, ``bad``: descripción textual de cada zona
    - ``status``: 'good' | 'warning' | 'danger' según donde caiga
      ``value`` respecto a las zonas
"""
from odoo import api, models


class GnFinancialDashboardIndicators(models.AbstractModel):
    _inherit = 'gn.financial.dashboard'

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    @api.model
    def get_indicators_data(self, filters):
        """RPC: devuelve la lista de indicadores con su gauge configurado."""
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        kpis = self._kpis_for_period(
            parsed, type_map, parsed['date_from'], parsed['date_to']
        )
        # Indicadores de cartera / pago (DSO, DPO).
        aging = self._aging(parsed)
        collection = self._collection_indicators(parsed, kpis, aging.get('receivable'))
        payment = self._payment_indicators(parsed, kpis, aging.get('payable'))

        items = self._build_indicators(kpis, collection, payment)
        return {
            'has_data': any(abs(it['value']) > 1e-6 for it in items),
            'currency': self._currency_payload(company.currency_id),
            'company_name': company.name,
            'period': {
                'date_from': parsed['date_from'].isoformat(),
                'date_to': parsed['date_to'].isoformat(),
            },
            'items': items,
        }

    # ------------------------------------------------------------------
    # Construcción de la lista
    # ------------------------------------------------------------------
    def _build_indicators(self, kpis, collection, payment):
        """Construye la lista de 10 indicadores tipo "punto de referencia"."""
        # Total de pasivo y patrimonio derivados de lo que ya hay en kpis
        # (`net_assets` = patrimonio; pasivo total = activos − patrimonio).
        total_assets = kpis.get('total_assets', 0.0) or 0.0
        equity = kpis.get('net_assets', 0.0) or 0.0
        total_liab = max(total_assets - equity, 0.0)
        current_liab = kpis.get('current_liab', 0.0) or 0.0
        cash_surplus = kpis.get('cash_surplus', 0.0) or 0.0

        debt_equity = (total_liab / equity) if equity > 0 else 0.0
        cash_flow_ratio = (cash_surplus / current_liab) if current_liab else 0.0

        items = [
            self._make_pct_indicator(
                key='gross_margin', name='Margen de ganancia bruta',
                formula='(Ventas netas − COGS) / Ventas netas',
                value=kpis.get('gross_margin', 0.0),
                bad=20.0, ok=50.0, max_val=100.0,
                ok_text='> 50%: el negocio es muy rentable',
                warn_text='> 20%: difícil pero aún rentable',
                bad_text='posible problema en el modelo de negocios',
            ),
            self._make_pct_indicator(
                key='net_margin', name='Margen de ganancias netas',
                formula='Ingreso neto / Ingresos',
                value=kpis.get('net_margin', 0.0),
                bad=3.0, ok=10.0, max_val=50.0,
                ok_text='> 10%: muy eficiente',
                warn_text='≥ 3%: eficiencia aceptable',
                bad_text='< 3%: no es eficiente al generar negocios',
            ),
            self._make_pct_indicator(
                key='operating_margin', name='Margen de operación',
                formula='EBIT / Ventas netas',
                value=kpis.get('operating_margin', 0.0),
                bad=5.0, ok=10.0, max_val=50.0,
                ok_text='> 10%: muy eficiente al operar negocios',
                warn_text='≥ 5%: eficiencia operativa razonable',
                bad_text='< 5%: posible problema en el costo de ventas',
            ),
            self._make_ratio_indicator(
                key='debt_to_equity', name='Deuda / capital',
                formula='Pasivo total / Patrimonio',
                value=debt_equity,
                ok_max=2.5, warn_max=5.0, max_val=10.0,
                direction='lower_better',
                ok_text='≤ 2.5: empresa madura, deuda controlada',
                warn_text='2.5 – 5: nivel de deuda moderado',
                bad_text='> 5: muchas deudas frente al patrimonio',
            ),
            self._make_ratio_indicator(
                key='current_ratio', name='Razón corriente',
                formula='Activos circulantes / Pasivos circulantes',
                value=kpis.get('current_ratio', 0.0),
                ok_min=1.5, warn_min=1.0, max_val=5.0,
                direction='higher_better',
                ok_text='> 1.5: buen rendimiento financiero',
                warn_text='≥ 1: cumple obligaciones de corto plazo',
                bad_text='< 1: rendimiento financiero débil',
            ),
            self._make_ratio_indicator(
                key='cash_flow_ratio', name='Proporción de flujo de efectivo',
                formula='Flujo de efectivo operativo / Pasivos circulantes',
                value=cash_flow_ratio,
                ok_min=1.0, warn_min=0.8, max_val=12.0,
                direction='higher_better',
                ok_text='> 1: el efectivo cubre las obligaciones',
                warn_text='≥ 0.8: cobertura cercana al objetivo',
                bad_text='< 0.8: ingresos pueden ser muy bajos',
            ),
            self._make_money_indicator(
                key='working_capital', name='Capital de trabajo',
                formula='Activos circulantes − Pasivos circulantes',
                value=kpis.get('working_capital', 0.0),
                ok_text='> 0: puede cumplir obligaciones',
                warn_text='≈ 0: holgura ajustada',
                bad_text='< 0: posible falta de efectivo a corto plazo',
            ),
            self._make_ratio_indicator(
                key='quick_ratio', name='Prueba ácida',
                formula='Activos rápidos / Pasivos circulantes',
                value=kpis.get('quick_ratio', 0.0),
                ok_min=1.0, warn_min=0.7, max_val=5.0,
                direction='higher_better',
                ok_text='> 1: empresa muy solvente',
                warn_text='≥ 0.7: solvencia razonable',
                bad_text='< 0.7: posibles problemas de liquidez',
            ),
            self._make_days_indicator(
                key='dso_days', name='Período promedio de cobro',
                formula='Cuentas por cobrar / Ventas a crédito × días del período',
                value=(collection or {}).get('dso') or 0.0,
                ok_max=45.0, warn_max=60.0, max_val=90.0,
                ok_text='≤ 45: cobra rápido',
                warn_text='≤ 60: cobra con suficiente rapidez',
                bad_text='> 60: posible problema en el acuerdo de pago',
            ),
            self._make_days_indicator(
                key='dpo_days', name='Promedio de días de pago',
                formula='Cuentas por pagar / Compras × días del período',
                value=(payment or {}).get('dpo') or 0.0,
                ok_max=45.0, warn_max=70.0, max_val=100.0,
                ok_text='≤ 45: paga rápido a proveedores',
                warn_text='≤ 70: ritmo de pago aceptable',
                bad_text='> 70: posibles problemas para pagar a proveedores',
            ),
            # ----- Indicadores adicionales (rentabilidad / eficiencia) -----
            self._make_pct_indicator(
                key='ebitda_margin', name='Margen EBITDA',
                formula='EBITDA / Ventas netas',
                value=kpis.get('ebitda_margin', 0.0),
                bad=10.0, ok=20.0, max_val=50.0,
                ok_text='> 20%: fuerte generación de caja operativa',
                warn_text='≥ 10%: generación de caja aceptable',
                bad_text='< 10%: baja generación de caja operativa',
            ),
            self._make_pct_indicator(
                key='roa', name='Rentabilidad sobre activos (ROA)',
                formula='Utilidad neta / Activos promedio',
                value=kpis.get('roa', 0.0),
                bad=2.0, ok=5.0, max_val=30.0,
                ok_text='> 5%: uso muy eficiente de los activos',
                warn_text='≥ 2%: eficiencia aceptable de los activos',
                bad_text='< 2%: los activos generan poca utilidad',
            ),
            self._make_pct_indicator(
                key='roe', name='Rentabilidad sobre patrimonio (ROE)',
                formula='Utilidad neta / Patrimonio promedio',
                value=kpis.get('roe', 0.0),
                bad=8.0, ok=15.0, max_val=50.0,
                ok_text='> 15%: excelente retorno para los socios',
                warn_text='≥ 8%: retorno aceptable para los socios',
                bad_text='< 8%: bajo retorno sobre el patrimonio',
            ),
            self._make_ratio_indicator(
                key='leverage_ratio', name='Apalancamiento financiero',
                formula='Activos promedio / Patrimonio promedio',
                value=kpis.get('leverage_ratio', 0.0),
                ok_max=2.0, warn_max=3.0, max_val=6.0,
                direction='lower_better',
                ok_text='≤ 2: estructura de capital saludable',
                warn_text='2 – 3: apalancamiento moderado',
                bad_text='> 3: dependencia alta del financiamiento',
            ),
            self._make_ratio_indicator(
                key='interest_coverage', name='Cobertura de intereses',
                formula='EBIT / Gasto financiero',
                value=kpis.get('interest_coverage', 0.0),
                ok_min=3.0, warn_min=1.5, max_val=15.0,
                direction='higher_better',
                ok_text='> 3: cubre con holgura los intereses',
                warn_text='≥ 1.5: cobertura justa de intereses',
                bad_text='< 1.5: riesgo para cubrir los intereses',
            ),
            self._make_ratio_indicator(
                key='assets_turnover', name='Rotación de activos',
                formula='Ventas netas / Activos promedio',
                value=kpis.get('assets_turnover', 0.0),
                ok_min=1.0, warn_min=0.5, max_val=4.0,
                direction='higher_better',
                ok_text='> 1: los activos generan ventas eficientemente',
                warn_text='≥ 0.5: rotación de activos aceptable',
                bad_text='< 0.5: activos poco productivos',
            ),
            self._make_ratio_indicator(
                key='inventory_turnover', name='Rotación de inventario',
                formula='COGS / Inventario promedio',
                value=kpis.get('inventory_turnover', 0.0),
                ok_min=6.0, warn_min=3.0, max_val=24.0,
                direction='higher_better',
                ok_text='> 6: inventario que rota con agilidad',
                warn_text='≥ 3: rotación de inventario aceptable',
                bad_text='< 3: inventario de baja rotación',
            ),
            self._make_ratio_indicator(
                key='ar_turnover', name='Rotación de cuentas por cobrar',
                formula='Ventas netas / Cuentas por cobrar promedio',
                value=kpis.get('ar_turnover', 0.0),
                ok_min=8.0, warn_min=4.0, max_val=24.0,
                direction='higher_better',
                ok_text='> 8: cobra rápido a sus clientes',
                warn_text='≥ 4: ritmo de cobro aceptable',
                bad_text='< 4: cobro lento de la cartera',
            ),
            self._make_ratio_indicator(
                key='ap_turnover', name='Rotación de cuentas por pagar',
                formula='Compras / Cuentas por pagar promedio',
                value=kpis.get('ap_turnover', 0.0),
                ok_min=4.0, warn_min=2.0, max_val=24.0,
                direction='higher_better',
                ok_text='> 4: paga a proveedores con regularidad',
                warn_text='≥ 2: ritmo de pago aceptable',
                bad_text='< 2: rotación baja de cuentas por pagar',
            ),
        ]
        return items

    # ------------------------------------------------------------------
    # Constructores por tipo de indicador
    # ------------------------------------------------------------------
    @staticmethod
    def _classify(value, low, high, direction):
        """Clasifica ``value`` en 'good' / 'warning' / 'danger' según las
        zonas y la dirección preferida."""
        if direction == 'higher_better':
            if value >= high:
                return 'good'
            if value >= low:
                return 'warning'
            return 'danger'
        # lower_better
        if value <= low:
            return 'good'
        if value <= high:
            return 'warning'
        return 'danger'

    def _make_pct_indicator(self, key, name, formula, value,
                            bad, ok, max_val,
                            ok_text='', warn_text='', bad_text=''):
        """Indicador en porcentaje (más alto es mejor)."""
        v = float(value or 0.0)
        return {
            'key': key, 'name': name, 'formula': formula,
            'value': v,
            'display': '%.1f%%' % v,
            'unit': 'pct',
            'min': 0.0, 'max': max_val,
            'direction': 'higher_better',
            'zones': [
                {'limit': bad, 'color': '#dc3545'},
                {'limit': ok, 'color': '#f59e0b'},
                {'limit': max_val, 'color': '#16a34a'},
            ],
            'ok': ok_text, 'warn': warn_text, 'bad': bad_text,
            'status': self._classify(v, bad, ok, 'higher_better'),
        }

    def _make_ratio_indicator(self, key, name, formula, value,
                              ok_min=None, warn_min=None,
                              ok_max=None, warn_max=None,
                              max_val=10.0, direction='higher_better',
                              ok_text='', warn_text='', bad_text=''):
        v = float(value or 0.0)
        if direction == 'higher_better':
            zones = [
                {'limit': warn_min, 'color': '#dc3545'},
                {'limit': ok_min, 'color': '#f59e0b'},
                {'limit': max_val, 'color': '#16a34a'},
            ]
            status = self._classify(v, warn_min, ok_min, 'higher_better')
        else:
            zones = [
                {'limit': ok_max, 'color': '#16a34a'},
                {'limit': warn_max, 'color': '#f59e0b'},
                {'limit': max_val, 'color': '#dc3545'},
            ]
            status = self._classify(v, ok_max, warn_max, 'lower_better')
        return {
            'key': key, 'name': name, 'formula': formula,
            'value': v,
            'display': '%.2f' % v,
            'unit': 'ratio',
            'min': 0.0, 'max': max_val,
            'direction': direction,
            'zones': zones,
            'ok': ok_text, 'warn': warn_text, 'bad': bad_text,
            'status': status,
        }

    def _make_days_indicator(self, key, name, formula, value,
                             ok_max, warn_max, max_val,
                             ok_text='', warn_text='', bad_text=''):
        """Días: menos es mejor (cobro/pago más rápido).

        Se aplica ``max(value, 0)`` para que valores negativos
        (cobros/pagos por encima de lo facturado en el período) no se
        traduzcan en agujas atrapadas a la izquierda; un valor 0 es lo
        ideal y se mostrará en la zona verde.
        """
        v = max(float(value or 0.0), 0.0)
        return {
            'key': key, 'name': name, 'formula': formula,
            'value': v,
            'display': '%.0f d' % v,
            'unit': 'days',
            'min': 0.0, 'max': max_val,
            'direction': 'lower_better',
            'zones': [
                {'limit': ok_max, 'color': '#16a34a'},
                {'limit': warn_max, 'color': '#f59e0b'},
                {'limit': max_val, 'color': '#dc3545'},
            ],
            'ok': ok_text, 'warn': warn_text, 'bad': bad_text,
            'status': self._classify(v, ok_max, warn_max, 'lower_better'),
        }

    def _make_money_indicator(self, key, name, formula, value,
                              ok_text='', warn_text='', bad_text=''):
        """Capital de trabajo y similares: positivo bueno, negativo malo."""
        v = float(value or 0.0)
        magnitude = max(abs(v), 1000.0)
        return {
            'key': key, 'name': name, 'formula': formula,
            'value': v,
            'display': self._format_compact(v),
            'unit': 'money',
            'min': -magnitude, 'max': magnitude,
            'direction': 'higher_better',
            'zones': [
                {'limit': 0.0, 'color': '#dc3545'},
                {'limit': magnitude * 0.05, 'color': '#f59e0b'},
                {'limit': magnitude, 'color': '#16a34a'},
            ],
            'ok': ok_text, 'warn': warn_text, 'bad': bad_text,
            'status': 'good' if v > magnitude * 0.05 else ('warning' if v >= 0 else 'danger'),
        }

    @staticmethod
    def _format_compact(value):
        n = float(value or 0.0)
        abs_n = abs(n)
        if abs_n >= 1e9:
            return '%.1fB' % (n / 1e9)
        if abs_n >= 1e6:
            return '%.1fM' % (n / 1e6)
        if abs_n >= 1e3:
            return '%.1fk' % (n / 1e3)
        return '{:,.0f}'.format(n)
