# -*- coding: utf-8 -*-
# Part of Wicoders Solution. See LICENSE file for full copyright and licensing

from odoo import models, api,_,fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    advance_payment_ids = fields.Many2many('account.payment', string="Advance Payment", copy=False)

    hide_payment_button = fields.Boolean(compute='_compute_hide_my_button')

    def advance_payment_button(self):
        return {
                'name': _("Advance Payment"),
                'type': 'ir.actions.act_window',
                'view_id': self.env.ref('wc_purchase_advance_payment.purchase_advance_account_payment_form_view_custom').id,
                'res_model': 'account.payment',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {
                    'default_payment_type': 'outbound',
                    'default_partner_type': 'supplier',
                    'search_default_outbound_filter': 1,
                    'res_partner_search_mode': 'supplier',
                    'default_partner_id': self.partner_id.id,
                    'default_ref': self.name,
                    'default_currency_id': self.currency_id.id,
                    'default_total_amount': self.amount_total,
                }
            }

    def action_advance_payment_view(self):
        action = self.env.ref('account.action_account_payments_payable').read()[0]
        action['domain'] = [('id', 'in', self.advance_payment_ids.ids)]
        action['context'] = {'create': False}
        return action


    def _compute_hide_my_button(self):
        param = self.env['ir.default'].sudo()._get('res.config.settings', 'enable_advance_payment_purchase')
        for rec in self:
            rec.hide_payment_button = True if param else False



