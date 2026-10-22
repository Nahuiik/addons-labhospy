# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    hospital_product_type = fields.Selection(
        selection_add=[
            ('bed', 'Bed'),
            ('vaccine', 'Vaccine'),
            ('insurance_plan', 'Insurance Plan'),
            ('surgery', 'Surgery'),
            ('dental', 'Dental Process'),
            ('procedure', 'Procedure'),
            ('pathology', 'Pathology'),
            ('radiology', 'Radiology'),
            ('consultation', 'Consultation'),
            ('disposable_material', 'Disposable Material'),
            ('toilet_supplies', 'Toilet Supplies'),
            ('paperwork_tools', 'Paperwork & Tools'),
            ('medical_service', 'Medical Service'),
            ('laboratory_service', 'Laboratory Service'),
            ('nutrition', 'Nutrition'),
            ('biopsias', 'Biopsies'),
            ('servicios_hospitalarios', 'Hospital Services'),
            ('emergencia', 'Emergency'),
        ]
    )

class accountInvoiceInh(models.Model):
    _inherit = "account.move"

    invoice_number = fields.Char(string="Invoice #",size=19, default="000-001-01-")

    # @api.constrains('invoice_number')
    # def validate_supplier_number(self):
    #     if self.type == 'out_invoice':
    #         if self.invoice_number and self.invoice_number != '000-001-01-':
    #             if len(self.invoice_number) < 19:
    #                 raise ValidationError(_("The invoice number should be equal to 19 characters"))
    #             for idx, val in enumerate(self.invoice_number):
    #                 if idx == 3 and not val == '-':
    #                     raise ValidationError(_("The invoice number does not have the correct format, the format correct is XXX-XXX-XX-XXXXXXXX"))
    #                 elif idx == 7 and not val == '-':
    #                     raise ValidationError(_("The invoice number does not have the correct format, the format correct is XXX-XXX-XX-XXXXXXXX"))
    #                 elif idx == 10 and not val == '-':
    #                     raise ValidationError(_("The invoice number does not have the correct format, the format correct is XXX-XXX-XX-XXXXXXXX"))
    #             return True
