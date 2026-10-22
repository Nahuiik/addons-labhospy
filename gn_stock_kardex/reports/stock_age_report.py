# -*- coding: utf-8 -*-
from odoo import api, models


class GnStockAgeReport(models.AbstractModel):
    _name = 'report.gn_stock_kardex.report_stock_age_template'
    _description = 'Stock Age Breakdown PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gn.stock.age.wizard'].browse(docids)
        w = wizard[0]
        rows, brackets = w._compute_age_data()
        bracket_labels = [b[0] for b in brackets]
        return {
            'doc_ids': docids,
            'wizard': w,
            'rows': rows,
            'bracket_labels': bracket_labels,
        }
