# -*- coding: utf-8 -*-
"""Catálogo genérico de visualizaciones (Chart.js + ECharts)."""

from odoo import _, api, models

# Gráficos avanzados → Apache ECharts (Apache 2.0)
ECHARTS_CHART_KEYS = frozenset({
    'movement_heatmap', 'pareto', 'waterfall', 'abc_analysis', 'xyz_analysis',
    'inventory_trend', 'monthly_inventory_value', 'supplier_performance',
    'warehouse_capacity', 'dead_stock_analysis', 'health_gauge',
    'top_categories', 'sales_vs_inventory',
})

CHARTJS_CHART_KEYS = frozenset({
    'top_products', 'receipts_vs_deliveries', 'receipt_status',
    'delivery_status', 'inventory_aging', 'stock_vs_reserved',
})


class InventoryDashboardViz(models.AbstractModel):
    _inherit = 'inventory.dashboard.service'

    @api.model
    def _build_viz_catalog(self, parsed, metrics):
        """Normaliza todas las visualizaciones a configuración genérica."""
        raw = super()._build_charts(parsed, metrics)
        catalog = {}
        for key, chart_def in raw.items():
            catalog[key] = self._normalize_viz(key, chart_def, parsed, metrics)
        return catalog

    @api.model
    def _normalize_viz(self, viz_id, chart_def, parsed, metrics):
        engine = 'echarts' if viz_id in ECHARTS_CHART_KEYS else 'chartjs'
        title = self._viz_title(viz_id)
        base = {
            'id': viz_id,
            'title': title,
            'engine': engine,
            'chart_type': chart_def.get('type', 'bar'),
            'drilldown': {'metric': viz_id, 'enabled': True},
            'export': ['png'],
            'fullscreen': True,
            'filters': self._filters_payload(parsed),
        }
        if engine == 'echarts':
            base['echarts_option'] = self._to_echarts_option(viz_id, chart_def, metrics)
            base['chartjs_def'] = None
        else:
            base['chartjs_def'] = chart_def
            base['echarts_option'] = None
        return base

    @api.model
    def _viz_title(self, viz_id):
        titles = {
            'movement_heatmap': _('Heatmap movimientos'),
            'pareto': _('Análisis Pareto'),
            'waterfall': _('Waterfall'),
            'abc_analysis': _('Análisis ABC'),
            'xyz_analysis': _('Análisis XYZ'),
            'inventory_trend': _('Tendencia inventario'),
            'monthly_inventory_value': _('Valor mensual inventario'),
            'supplier_performance': _('Desempeño proveedores'),
            'warehouse_capacity': _('Capacidad almacén'),
            'dead_stock_analysis': _('Stock muerto'),
            'health_gauge': _('Gauge salud'),
            'top_categories': _('Top categorías'),
            'sales_vs_inventory': _('Ventas vs inventario'),
            'top_products': _('Top productos'),
            'receipts_vs_deliveries': _('Recepciones vs entregas'),
            'receipt_status': _('Estado recepciones'),
            'delivery_status': _('Estado entregas'),
            'inventory_aging': _('Antigüedad inventario'),
            'stock_vs_reserved': _('Disponible vs reservado'),
        }
        return titles.get(viz_id, viz_id)

    @api.model
    def _to_echarts_option(self, viz_id, chart_def, metrics):
        labels = chart_def.get('labels') or []
        values = chart_def.get('values') or []
        datasets = chart_def.get('datasets') or []

        if viz_id == 'movement_heatmap':
            matrix = chart_def.get('matrix') or []
            heat_data = []
            for wi, row in enumerate(matrix):
                for di, val in enumerate(row):
                    if val:
                        heat_data.append([di, wi, val])
            return {
                'tooltip': {'position': 'top'},
                'grid': {'height': '70%', 'top': '10%'},
                'xAxis': {'type': 'category', 'data': labels, 'splitArea': {'show': True}},
                'yAxis': {'type': 'category', 'data': [f'S{i+1}' for i in range(len(matrix))], 'splitArea': {'show': True}},
                'visualMap': {
                    'min': 0, 'max': max((v for row in matrix for v in row), default=1),
                    'calculable': True, 'orient': 'horizontal', 'left': 'center', 'bottom': '0%',
                },
                'series': [{
                    'type': 'heatmap', 'data': heat_data,
                    'emphasis': {'itemStyle': {'shadowBlur': 10, 'shadowColor': 'rgba(0,0,0,0.4)'}},
                }],
                'toolbox': self._echarts_toolbox(),
                'dataZoom': [{'type': 'inside'}, {'type': 'slider'}],
            }

        if viz_id == 'pareto':
            cum = 0
            total = sum(values) or 1
            cum_pct = []
            for v in values:
                cum += v
                cum_pct.append(round(cum / total * 100, 1))
            return {
                'tooltip': {'trigger': 'axis'},
                'legend': {'data': [_('Cantidad'), _('Acumulado %')]},
                'xAxis': [{'type': 'category', 'data': labels, 'axisLabel': {'rotate': 30}}],
                'yAxis': [
                    {'type': 'value', 'name': _('Cantidad')},
                    {'type': 'value', 'name': '%', 'max': 100},
                ],
                'series': [
                    {'name': _('Cantidad'), 'type': 'bar', 'data': values, 'itemStyle': {'color': '#2563eb'}},
                    {'name': _('Acumulado %'), 'type': 'line', 'yAxisIndex': 1, 'data': cum_pct, 'itemStyle': {'color': '#dc2626'}},
                ],
                'toolbox': self._echarts_toolbox(),
                'dataZoom': [{'type': 'inside'}, {'type': 'slider'}],
            }

        if viz_id == 'waterfall':
            vals = chart_def.get('values') or []
            return {
                'tooltip': {'trigger': 'axis'},
                'xAxis': {'type': 'category', 'data': labels},
                'yAxis': {'type': 'value'},
                'series': [{
                    'type': 'bar',
                    'stack': 'total',
                    'data': [
                        {'value': abs(vals[0]) if len(vals) > 0 else 0, 'itemStyle': {'color': '#059669'}},
                        {'value': -abs(vals[1]) if len(vals) > 1 else 0, 'itemStyle': {'color': '#dc2626'}},
                        {'value': abs(vals[2]) if len(vals) > 2 else 0, 'itemStyle': {'color': '#2563eb'}},
                    ],
                }],
                'toolbox': self._echarts_toolbox(),
            }

        if viz_id == 'abc_analysis':
            ds = datasets[0] if datasets else {}
            return {
                'tooltip': {'trigger': 'axis'},
                'xAxis': {'type': 'category', 'data': labels},
                'yAxis': {'type': 'value'},
                'series': [{'type': 'bar', 'stack': 'abc', 'data': ds.get('data', values), 'itemStyle': {'borderRadius': [4, 4, 0, 0]}}],
                'toolbox': self._echarts_toolbox(),
            }

        if viz_id == 'xyz_analysis':
            return {
                'tooltip': {'trigger': 'item'},
                'series': [{
                    'type': 'pie', 'radius': ['40%', '70%'],
                    'data': [{'name': n, 'value': v} for n, v in zip(labels, values)],
                }],
                'toolbox': self._echarts_toolbox(),
            }

        if viz_id == 'health_gauge':
            score = chart_def.get('value') or metrics.get('inventory_accuracy', {}).get('value', 0)
            if isinstance(score, dict):
                score = 0
            return {
                'series': [{
                    'type': 'gauge',
                    'startAngle': 200, 'endAngle': -20,
                    'min': 0, 'max': 100,
                    'progress': {'show': True, 'width': 14},
                    'axisLine': {'lineStyle': {'width': 14}},
                    'detail': {'valueAnimation': True, 'formatter': '{value}%', 'fontSize': 22},
                    'data': [{'value': score, 'name': _('Salud')}],
                }],
                'toolbox': self._echarts_toolbox(),
            }

        if viz_id == 'top_categories':
            return {
                'tooltip': {'trigger': 'item'},
                'series': [{
                    'type': 'treemap',
                    'data': [{'name': n, 'value': v} for n, v in zip(labels, values)],
                    'leafDepth': 1,
                }],
                'toolbox': self._echarts_toolbox(),
            }

        if viz_id in ('inventory_trend', 'monthly_inventory_value'):
            return {
                'tooltip': {'trigger': 'axis'},
                'xAxis': {'type': 'category', 'data': labels},
                'yAxis': {'type': 'value'},
                'series': [{
                    'type': 'line', 'smooth': True, 'areaStyle': {'opacity': 0.15},
                    'data': values, 'itemStyle': {'color': '#2563eb'},
                }],
                'toolbox': self._echarts_toolbox(),
                'dataZoom': [
                    {'type': 'inside', 'xAxisIndex': 0},
                    {'type': 'slider', 'xAxisIndex': 0},
                ],
                'brush': {'toolbox': ['lineX', 'clear']},
            }

        if viz_id in ('supplier_performance', 'warehouse_capacity', 'dead_stock_analysis'):
            return {
                'tooltip': {'trigger': 'axis'},
                'grid': {'left': '20%', 'right': '4%'},
                'xAxis': {'type': 'value'},
                'yAxis': {'type': 'category', 'data': labels, 'inverse': True},
                'series': [{'type': 'bar', 'data': values, 'itemStyle': {'borderRadius': [0, 4, 4, 0]}}],
                'toolbox': self._echarts_toolbox(),
                'dataZoom': [{'type': 'inside', 'yAxisIndex': 0}, {'type': 'slider', 'yAxisIndex': 0}],
            }

        if viz_id == 'sales_vs_inventory':
            return {
                'tooltip': {'trigger': 'axis'},
                'legend': {'data': [_('Valor')]},
                'xAxis': {'type': 'category', 'data': labels},
                'yAxis': {'type': 'value'},
                'series': [{'type': 'bar', 'data': values}],
                'toolbox': self._echarts_toolbox(),
            }

        # fallback bar
        return {
            'tooltip': {'trigger': 'axis'},
            'xAxis': {'type': 'category', 'data': labels},
            'yAxis': {'type': 'value'},
            'series': [{'type': 'bar', 'data': values}],
            'toolbox': self._echarts_toolbox(),
        }

    @api.model
    def _echarts_toolbox(self):
        return {
            'feature': {
                'saveAsImage': {'title': _('PNG')},
                'dataZoom': {'title': {'zoom': _('Zoom'), 'back': _('Reset')}},
                'restore': {'title': _('Restaurar')},
            },
        }

    @api.model
    def _build_charts(self, parsed, metrics):
        """Delegado: el catálogo viz usa charts crudos de phase2."""
        return super()._build_charts(parsed, metrics)
