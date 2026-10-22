# -*- coding: utf-8 -*-
from odoo import api, models


class ReportRetentionMonthlySummary(models.AbstractModel):
    _name = 'report.l10n_hn_retentions.retention_monthly_summary'
    _description = 'Resumen mensual de retenciones (QWeb)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hn.retention.monthly.wizard'].browse(docids)
        doc = docs[:1]
        if not doc:
            return {
                'doc_ids': docids,
                'doc_model': 'hn.retention.monthly.wizard',
                'docs': docs,
                'lines': [],
                'date_from': False,
                'date_to': False,
                'total_retention': 0.0,
            }
        lines, date_from, date_to = doc._collect_rows()
        total = sum(float(r['monto'] or 0.0) for r in lines)
        return {
            'doc_ids': docids,
            'doc_model': 'hn.retention.monthly.wizard',
            'docs': docs,
            'lines': lines,
            'date_from': date_from,
            'date_to': date_to,
            'total_retention': total,
        }
