# -*- coding: utf-8 -*-

import json

from odoo import fields, models


class InvoicePaymentExecutiveWizard(models.TransientModel):
    _name = 'gn.accounting.invoice.payment.executive.wizard'
    _description = 'Exportación ejecutiva facturas y pagos'

    company_id = fields.Many2one('res.company', required=True)
    filter_json = fields.Text(string='Filtros JSON', required=True)
    dashboard_json = fields.Text(string='Datos tablero JSON')

    def prepare_from_filters(self, filters=None):
        """Genera payload del tablero para la plantilla QWeb ejecutiva."""
        self.ensure_one()
        import json
        service = self.env['gn.accounting.invoice.payment.service']
        filt = filters or json.loads(self.filter_json or '{}')
        data = service.get_dashboard_init(filt)
        self.write({'dashboard_json': json.dumps(data, default=str)})
        return self
