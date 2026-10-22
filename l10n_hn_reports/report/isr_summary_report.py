# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.misc import formatLang

from odoo.addons.l10n_hn_reports.models.report_branding import company_report_branding


def _format_date_dmy(value):
    if value is False or value is None:
        return ''
    if isinstance(value, str):
        try:
            value = fields.Date.from_string(value)
        except (ValueError, TypeError):
            return value
    try:
        return fields.Date.to_date(value).strftime('%d/%m/%Y')
    except (AttributeError, TypeError):
        return str(value)


class ReportIsrSummary(models.AbstractModel):
    _name = 'report.l10n_hn_reports.isr_summary_report'
    _description = 'Resumen ISR (QWeb)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hn.isr.summary.wizard'].browse(docids)
        doc = docs[:1]
        comp = doc.company_id if doc else self.env.company
        branding = company_report_branding(comp)
        if not doc:
            return {
                'doc_ids': docids,
                'doc_model': 'hn.isr.summary.wizard',
                'docs': docs,
                'lines': [],
                'date_from_fmt': '',
                'date_to_fmt': '',
                'total_debe_fmt': formatLang(self.env, 0.0, grouping=True, digits=2),
                'total_haber_fmt': formatLang(self.env, 0.0, grouping=True, digits=2),
                **branding,
            }
        rows, date_from, date_to, accounts = doc._collect_rows()
        t_debe = sum(float(r['debe'] or 0.0) for r in rows)
        t_haber = sum(float(r['haber'] or 0.0) for r in rows)
        acct_label = ', '.join(
            '%s %s' % (a.code or '', a.name or '') for a in accounts[:20]
        )
        if len(accounts) > 20:
            acct_label += '...'
        display_lines = []
        for r in rows:
            display_lines.append({
                **r,
                'fecha_fmt': _format_date_dmy(r.get('fecha')),
                'debe_fmt': formatLang(self.env, float(r.get('debe') or 0.0), grouping=True, digits=2),
                'haber_fmt': formatLang(self.env, float(r.get('haber') or 0.0), grouping=True, digits=2),
            })
        return {
            'doc_ids': docids,
            'doc_model': 'hn.isr.summary.wizard',
            'docs': docs,
            'lines': display_lines,
            'date_from': date_from,
            'date_to': date_to,
            'date_from_fmt': _format_date_dmy(date_from),
            'date_to_fmt': _format_date_dmy(date_to),
            'accounts_label': acct_label,
            'total_debe': t_debe,
            'total_haber': t_haber,
            'total_debe_fmt': formatLang(self.env, t_debe, grouping=True, digits=2),
            'total_haber_fmt': formatLang(self.env, t_haber, grouping=True, digits=2),
            **branding,
        }
