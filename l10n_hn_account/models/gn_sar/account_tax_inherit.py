from odoo import models, fields, api, _


class AccountTax(models.Model):
    _inherit = 'account.tax'
    
    is_exonerate = fields.Boolean(string="Es exonerado")
    is_exempt = fields.Boolean(string="Es exento")