# -*- coding: utf-8 -*-

import json

from odoo import api, models


class ReportTraceabilityDocument(models.AbstractModel):
    _name = 'report.gn_product_traceability_widget.traceability_pdf'
    _description = 'Product Traceability PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        filters = data.get('filters') or {}
        if isinstance(filters, str):
            filters = json.loads(filters)
        if not filters.get('product_id') and docids:
            filters = {**filters, 'product_id': docids[0]}
        payload = self.env['product.traceability.service'].get_export_data(filters)
        product_id = payload['product']['id']
        products = self.env['product.product'].browse(docids or [product_id])
        return {
            'doc_ids': products.ids,
            'doc_model': 'product.product',
            'docs': products,
            'company': self.env.company,
            'payload': payload,
        }
