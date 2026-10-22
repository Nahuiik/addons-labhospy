# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import _, api, models


class PurchaseDashboardExport(models.AbstractModel):
    _inherit = 'purchase.dashboard.service'

    @api.model
    def export_kpis_csv(self, filters=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        compare = self._comparison_parsed(parsed)
        cache = {}
        current = self._compute_metrics(parsed, cache)
        previous = self._compute_metrics(compare, cache) if compare else {}
        kpis = self._build_kpi_cards(current, previous, parsed, cache)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([_('Indicador'), _('Valor'), _('Variación %')])
        for k in kpis:
            writer.writerow([k['label'], k['value'], k.get('variation_pct', '')])
        content = output.getvalue().encode('utf-8-sig')
        return {
            'filename': 'compras_kpis.csv',
            'data': base64.b64encode(content).decode('ascii'),
            'mimetype': 'text/csv',
        }

    @api.model
    def get_executive_report_action(self, filters=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        cache = {}
        compare = self._comparison_parsed(parsed)
        current = self._compute_metrics(parsed, cache)
        previous = self._compute_metrics(compare, cache) if compare else {}
        advanced = self._build_summary_advanced(parsed, cache, current, previous)
        data = {
            'filters': self._filters_payload(parsed),
            'kpis': self._build_kpi_cards(current, previous, parsed, cache)[:20],
            'health': advanced.get('health', {}),
            'alerts': advanced.get('alerts', {}).get('items', [])[:10],
            'insights': advanced.get('insights', [])[:6],
            'user_name': self.env.user.name,
        }
        return self.env.ref('gn_purchase_dashboard.action_report_purchase_executive').report_action(
            parsed['company'].ids,
            data={'report_data': data},
        )

    @api.model
    def export_widgets_csv(self, filters=None, widget_key='top_vendors'):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        cache = {}
        builders = self._widget_builders()
        fn = builders.get(widget_key)
        if not fn:
            return {'filename': 'compras.csv', 'data': '', 'mimetype': 'text/csv'}
        widget = fn(parsed, cache)
        output = io.StringIO()
        writer = csv.writer(output)
        rows = widget.get('rows') or widget.get('top') or []
        if rows:
            writer.writerow(list(rows[0].keys()))
            for row in rows:
                writer.writerow([row.get(k, '') for k in rows[0].keys()])
        content = output.getvalue().encode('utf-8-sig')
        return {
            'filename': f'compras_{widget_key}.csv',
            'data': base64.b64encode(content).decode('ascii'),
            'mimetype': 'text/csv',
        }
