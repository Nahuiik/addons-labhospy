from odoo import models, fields, api, _


class res_partner(models.Model):
    _inherit = 'res.partner'
    
    is_exonerated = fields.Boolean(string="Es Exonerado?")
    no = fields.Boolean(string="no", help="This field is added because odoo enterprise has an error when the system is in Spanish.")
    