# -*- coding: utf-8 -*-
from odoo import api, models, _

class IsvReport(models.AbstractModel):
    _name = 'report.l10n_hn_account.isv_report_view'
    _description = 'Reporte ISV'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        month = self.get_month(data.get('month'))
        info_data = self.get_data(month, data.get('fiscal_credit'), data.get('pos'))
        return {
            'doc_ids': data.get('ids', docids),
            'doc_model': data.get('model', 'l10n_hn_account.wizard_isv_report'),
            'docs': info_data,
        }

    @api.model
    def get_month(self, month):
        meses = {
            'january': 'Enero', 'february': 'Febrero', 'march': 'Marzo', 
            'april': 'Abril', 'may': 'Mayo', 'june': 'Junio', 'july': 'Julio', 
            'august': 'Agosto', 'september': 'Septiembre', 'october': 'Octubre', 
            'november': 'Noviembre', 'december': 'Diciembre'
        }
        return meses.get(month, 'Desconocido')

    @api.model
    def get_data(self, month, credit, pos):
        sales = self.env['libro.ventas.forecast'].search([('month', '=', month)])
        purchases = self.env['libro.compras.forecast'].search([('month', '=', month)])
        
        info = {
            'net_sale': 0, 'taxed_sale': 0, 'exonerated_sale': 0, 'total_sale': 0,
            'net_purchase': 0, 'taxed_purchase': 0, 'exonerated_purchase': 0, 'total_purchase': 0,
            'credit_fiscal': float(credit), 'pos': float(pos), 'year': 0, 'month': month
        }
        
        tax_sale, tax_purchase, year = 0, 0, 0

        for sale in sales:
            tax_sale = sale.sub_total * 0.15
            info.update({
                'net_sale': sale.sub_total, 'taxed_sale': tax_sale, 
                'exonerated_sale': sale.total_exento, 'total_sale': sale.total_incoming,
                'year': sale.year
            })

        for purchase in purchases:
            tax_purchase = purchase.sub_total * 0.15
            info.update({
                'net_purchase': purchase.sub_total, 'taxed_purchase': tax_purchase,
                'exonerated_purchase': purchase.total_exento, 'total_purchase': purchase.total_incoming,
                'year': purchase.year
            })

        tax_total = tax_sale - tax_purchase
        info.update({'to_pay': tax_total, 'total': tax_total - credit - pos})

        return [info]