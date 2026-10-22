# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import api, models, _


class SummaryInvoiceReport(models.AbstractModel):
    _name = 'report.gn_hospital_product.summary_invoice_report'
    _description = 'Hospital Summary Invoice Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        info_data, values = self.get_data(docids)
        return {
            'docs': info_data,
            'vals':values,
        }

    def get_data(self, ids):
        obj_invoice = self.env['account.move'].browse(ids)
        info_invoice = []
        style = self.env['report.template.settings'].search([], limit=1)
        vals = {}
        for inv in obj_invoice:
            # Get all categories in invoice lines

            category_ids = inv.invoice_line_ids.mapped('product_id.categ_id.id')

            # category_price is the same for all products in the same category in the invoice lines

            for category in category_ids:
                info_invoice.append({
                    'category': self.env['product.category'].browse(category).name,
                    'amount': sum(inv.invoice_line_ids.filtered(lambda x: x.product_id.categ_id.id == category).mapped('price_total')),
                    'description': self.env['product.category'].browse(category).name,
                    'category_price': inv.invoice_line_ids.filtered(lambda x: x.product_id.categ_id.id == category).mapped('price_unit')[0],
                    'quantity_products': sum(int(line.quantity) for line in inv.invoice_line_ids if line.product_id.categ_id.id == category)
                })

            vals = {
                'origin': 'inv.origin',
                'payment_term': 'inv.invoice_payments_widget.name',
                'total': inv.amount_total,
                'reference': inv.name,
                'style': style,
                'number': inv.name,
                'min_number_shot': inv.min_number_shot,
                'max_number_shot': inv.max_number_shot,
                'cai_shot': inv.cai_shot,
                'cai_expires_shot': inv.cai_expires_shot,
                'client_details': self.get_client_details(inv),
                'inv': inv
            }
        return info_invoice, vals


    @api.model
    def get_client_details(self, invoice):
        partner = invoice.partner_id
        if not partner:
            return {'name': _('Final Consumer'), 'rtn': '', 'phone': False}

        phone = partner.phone or partner.mobile or False
        return {
            'name': partner.display_name,
            'rtn': partner.rtn or '',
            'phone': phone,
        }

    @staticmethod
    def assign_id(type_code):
        mapping = {
            'medicament': (1, _('Medicament')),
            'bed': (2, _('Bed')),
            'vaccine': (3, _('Vaccine')),
            'insurance_plan': (4, _('Insurance Plan')),
            'surgery': (5, _('Surgery')),
            'procedure': (6, _('Procedure')),
            'fdrinks': (7, _('Drinks')),
            'pathology': (8, _('Pathology')),
            'radiology': (10, _('Radiology')),
            'consultation': (11, _('Consultation')),
            'disposable_material': (12, _('Disposable Material')),
            'toilet_supplies': (13, _('Toilet Supplies')),
            'paperwork_tools': (14, _('Paperwork Tools')),
            'medical_service': (16, _('Medical Service')),
            'laboratory_service': (17, _('Laboratory Service')),
            'nutrition': (18, _('Nutrition')),
            'os': (19, _('Others')),
            'biopsias': (20, _('Biopsies')),
            'emergencia': (21, _('Emergency')),
            'servicios_hospitalarios': (22, _('Hospital Services')),
        }
        identifier, name = mapping.get(type_code, (0, _('None')))
        return {'id': identifier, 'name': name}

    def change_format(self,date):
        return datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
