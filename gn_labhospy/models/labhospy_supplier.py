from odoo import fields, models


class LabHosPySupplier(models.Model):
    _name = 'gn.labhospy.supplier'
    _description = 'Proveedor de catálogo (LabHosPy)'
    _order = 'name'

    name = fields.Char(string='Proveedor', required=True)
    reference = fields.Char(string='Referencia')
    active = fields.Boolean(default=True)

