# -*- coding: utf-8 -*-
from odoo import api, models

from odoo.addons.l10n_hn_reports.models.report_branding import company_report_branding


class ReportHnIsvDeclaracion(models.AbstractModel):
    _name = 'report.l10n_hn_reports.hn_isv_declaracion'
    _description = 'Reporte ISV (QWeb)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hn.reporte.isv.wizard'].browse(docids)
        vals = docs[:1]._prepare_qweb_values()
        vals.update(company_report_branding(docs[:1].company_id))
        vals.update({
            'doc_ids': docids,
            'doc_model': 'hn.reporte.isv.wizard',
            'docs': docs,
        })
        return vals
