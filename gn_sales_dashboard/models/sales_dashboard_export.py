# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import _, api, models


class SalesDashboardExport(models.AbstractModel):
    _inherit = 'sales.dashboard.service'

    @api.model
    def export_kpis_csv(self, filters=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        compare = self._comparison_parsed(parsed)
        kpis = self._build_kpi_cards(parsed, self._compute_metrics(parsed),
                                     self._compute_metrics(compare) if compare else {})
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([_('Indicador'), _('Valor'), _('Variación %'), _('Fuente')])
        for k in kpis:
            writer.writerow([k['label'], k['value'], k.get('variation_pct', ''), k.get('source', '')])
        content = output.getvalue().encode('utf-8-sig')
        return {
            'filename': 'ventas_kpis.csv',
            'data': base64.b64encode(content).decode('ascii'),
            'mimetype': 'text/csv',
        }

    @api.model
    def export_table_csv(self, filters=None, table_key='recent_invoices'):
        self._check_dashboard_access()
        page = self.get_table_page(filters, table_key, 1, 500, '', '')
        output = io.StringIO()
        writer = csv.writer(output)
        cols = page.get('columns', [])
        writer.writerow([c['label'] for c in cols])
        for row in page.get('rows', []):
            writer.writerow([row.get(c['key'], '') for c in cols])
        content = output.getvalue().encode('utf-8-sig')
        return {
            'filename': f'ventas_{table_key}.csv',
            'data': base64.b64encode(content).decode('ascii'),
            'mimetype': 'text/csv',
        }

    @api.model
    def get_executive_report_action(self, filters=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        core = self.get_dashboard_core(filters)
        advanced = self.get_dashboard_advanced(filters, ['health', 'goal_tracker', 'alerts'])
        data = {
            'filters': self._filters_payload(parsed),
            'kpis': core.get('kpis', [])[:20],
            'health': advanced.get('advanced', {}).get('health', {}),
            'goal': advanced.get('advanced', {}).get('goal_tracker', {}),
            'alerts': advanced.get('advanced', {}).get('alerts', {}).get('items', [])[:10],
            'user_name': self.env.user.name,
        }
        return self.env.ref('gn_sales_dashboard.action_report_sales_executive').report_action(
            parsed['company'].ids,
            data={'report_data': data},
        )
