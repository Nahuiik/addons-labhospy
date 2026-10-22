# -*- coding: utf-8 -*-
from odoo import api, models


class ReportHnLibroStd(models.AbstractModel):
    _name = 'report.l10n_hn_reports.hn_libro_std'
    _description = 'Libro de compras/ventas HN — formato estándar (QWeb)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hn.libro.report'].browse(docids)
        vals = docs[:1]._prepare_qweb_values(layout='estandar')
        vals.update({
            'doc_ids': docids,
            'doc_model': 'hn.libro.report',
            'docs': docs,
        })
        return vals


class ReportHnLibroResumen(models.AbstractModel):
    _name = 'report.l10n_hn_reports.hn_libro_resumen'
    _description = 'Libro compras/ventas — resumen ejecutivo (QWeb)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hn.libro.report'].browse(docids)
        vals = docs[:1]._prepare_qweb_values(layout='resumen')
        vals.update({
            'doc_ids': docids,
            'doc_model': 'hn.libro.report',
            'docs': docs,
        })
        return vals
