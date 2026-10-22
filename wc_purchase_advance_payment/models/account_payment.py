# -*- coding: utf-8 -*-
# Part of Wicoders Solution. See LICENSE file for full copyright and licensing

from odoo import fields, models,_,api
from odoo.exceptions import ValidationError


class account_payment(models.Model):
    _inherit = 'account.payment'

    create_in_state_purchase = fields.Selection([('draft', 'Draft'),
                                                 ('confirm', 'Confirm')],
                                                default='confirm',
                                                string="Payment Status")
    total_amount = fields.Monetary(
        string="Total Amount"
    )

    due_amount = fields.Monetary(
        string="Remaining Amount",
        compute='_compute_total_amount'
    )

    @api.depends('amount')
    def _compute_total_amount(self):
        if self._context.get('default_total_amount'):
            total_amount = self._context.get('default_total_amount')
            self.due_amount = total_amount - self.amount
        else:
            self.due_amount = 0.0

    def create_advance_payment(self):
        if self.amount <= 0.0:
            raise ValidationError(_("The payment amount must be greater than zero.."))
        if self.create_in_state_purchase == 'confirm':
            self.action_post()
        if self.env.context.get('active_id'):
            purchase_id = self.env['purchase.order'].browse(self.env.context.get('active_id'))
            purchase_id.write({'advance_payment_ids': [(4, self.id)]})
        return True