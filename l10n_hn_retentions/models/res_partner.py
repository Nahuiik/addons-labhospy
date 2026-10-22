from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_payment_account = fields.Boolean(string='Payment Account')
    # account_to_payment = fields.Char(string='')
    date_payments_account = fields.Date(string='Payment Account Date')
    file_account_pay_ids = fields.Many2many(
        'payment.account.tofile',
        'res_partner_payment_file_rel',
        'partner_id',
        'file_id',
        string='Payment Account Files'
    )


class PaymentAccountTofile(models.Model):
    _name = 'payment.account.tofile'
    _description = 'Payment Account Files for Suppliers'

    _rec_name = 'name'
    _order = 'name ASC'

    name = fields.Char(string='Description', required=True)
    file_payment_account = fields.Binary(string='File', attachment=True)
    date_file = fields.Date(string='Date', default=fields.Date.today)
