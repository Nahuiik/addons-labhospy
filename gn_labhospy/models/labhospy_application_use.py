from odoo import fields, models


class GnLabhospyApplicationUse(models.Model):
    _name = 'gn.labhospy.application.use'
    _description = 'Aplicación / uso (LabHosPy)'
    _order = 'name'

    name = fields.Char(string='Descripción', required=True, translate=True)
    reference = fields.Char(string='Referencia')
    active = fields.Boolean(default=True)
