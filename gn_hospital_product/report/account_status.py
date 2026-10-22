# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.tools.misc import format_date


class AccountStatusReport(models.AbstractModel):
    _name = 'report.gn_hospital_product.account_status_report'
    _description = 'Hospital Account Status Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        invoices = self.env['account.move'].browse(docids)
        info_data, values = self._prepare_data(invoices)
        return {
            'docs': info_data,
            'vals': values,
        }

    def _prepare_data(self, invoices):
        category_totals = defaultdict(lambda: {'category': '', 'amount': 0.0})
        report_vals = {}

        for invoice in invoices:
            for line in invoice.invoice_line_ids.filtered(lambda l: l.product_id):
                type_data = self._assign_id(line.product_id.hospital_product_type)
                category_entry = category_totals[type_data['id']]
                category_entry['category'] = type_data['name']
                category_entry['amount'] += line.price_subtotal

            report_vals = {
                'date': invoice.invoice_date,
                'total': sum(cat['amount'] for cat in category_totals.values()),
                'reference': invoice.name,
                'partner': invoice.partner_id.display_name or '',
            }

        if report_vals.get('date'):
            report_vals['date'] = format_date(self.env, report_vals['date'])
        else:
            report_vals['date'] = ''

        return list(category_totals.values()), report_vals

    @staticmethod
    def _assign_id(product_type):
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
        identifier, name = mapping.get(product_type, (0, _('None')))
        return {'id': identifier, 'name': name}
