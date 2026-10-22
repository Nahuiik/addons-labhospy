# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

class cashSettlementWizard(models.TransientModel):
    _name = "gn_arqueo_caja.cash_settlement_wizard"
    _description = "Cash Settlement Wizard"

    date_from   = fields.Date(string="Desde", required=True, default=fields.Date.context_today)
    date_to     = fields.Date(string="Hasta", required=True, default=fields.Date.context_today)
    cashier_ids = fields.Many2many('res.users', string="Cajeros")

    @api.constrains('date_from','date_to')
    def _validate_dates(self):
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValidationError(_('La fecha inicial no puede ser mayor que la fecha final.'))

    def export_xls(self):
        domain = [
            ('payment_type', '=', 'inbound'),
            ('state', 'in', ['posted', 'paid']),
            ('create_uid', 'in', self.cashier_ids.ids),
        ]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        if not self.env['account.payment'].search(domain, limit=1):
            raise ValidationError(_("No ha tenido ventas ese día."))

        context = self.env.context
        datas = {'ids': context.get('active_ids', []),'date_from':self.date_from,'date_to':self.date_to, 'cashier_ids':self.cashier_ids.ids}
        datas['model'] = 'gn_arqueo_caja.cash_settlement_wizard'
        datas['form'] = self.read()[0]
        for field in datas['form'].keys():
            if isinstance(datas['form'][field], tuple):
                datas['form'][field] = datas['form'][field][0]
        if context.get('xls_export'):
            return self.env.ref('gn_arqueo_caja.action_cash_settlement_xls').report_action(self, data=datas)