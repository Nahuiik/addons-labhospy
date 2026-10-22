from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    gn_labhospy_application_use_id = fields.Many2one(
        'gn.labhospy.application.use',
        string='Aplicación / uso',
    )
    gn_labhospy_application_use = fields.Text(
        string='Aplicación de uso (SC) texto',
        help='Texto complementario opcional junto al catálogo.',
    )
    gn_labhospy_product_is_controlled = fields.Boolean(
        string='Producto SC',
        related='product_id.product_tmpl_id.gn_labhospy_is_controlled',
    )
