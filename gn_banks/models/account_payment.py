# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_move_type = fields.Selection([('check', 'Cheques'),
                                          ('cash', 'Cash'), ('transference', 'Transfer'),
                                          ('otro', 'Otro')], string="Payment Transaction Type", default="cash")
    def action_print_cheq_desktop(self):
        return self.env.ref('gn_banks.account_payment_desktop_check').report_action(self)
    def action_print_tranference(self):
        return self.env.ref('gn_banks.account_payment_tranference').report_action(self)
    