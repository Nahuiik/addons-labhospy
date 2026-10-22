# -*- coding: utf-8 -*-

from odoo import fields, models


class TraceabilityExportWizard(models.TransientModel):
    _name = 'traceability.export.wizard'
    _description = 'Traceability Export Wizard'

    product_id = fields.Many2one('product.product', required=True)
    lot_id = fields.Many2one('stock.lot')
    date_from = fields.Date()
    date_to = fields.Date()
    export_type = fields.Selection([
        ('pdf', 'PDF'),
        ('xlsx', 'Excel'),
    ], default='pdf', required=True)

    def action_export(self):
        self.ensure_one()
        filters = {
            'product_id': self.product_id.id,
            'lot_id': self.lot_id.id if self.lot_id else False,
            'date_from': fields.Date.to_string(self.date_from) if self.date_from else False,
            'date_to': fields.Date.to_string(self.date_to) if self.date_to else False,
        }
        report_xmlid = (
            'gn_product_traceability_widget.action_traceability_report_pdf'
            if self.export_type == 'pdf'
            else 'gn_product_traceability_widget.action_traceability_report_xlsx'
        )
        report = self.env.ref(report_xmlid)
        return report.report_action(self.product_id, data={'filters': filters})
