# -*- coding: utf-8 -*-
from odoo import api, models


class ReportInventoryExecutive(models.AbstractModel):
    _name = 'report.dev_advance_inventory_dashboard.inv_exec'
    _description = 'Reporte ejecutivo de inventario'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        companies = self.env['res.company'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'res.company',
            'docs': companies,
            'report_data': data,
        }
