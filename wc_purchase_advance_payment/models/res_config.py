# -*- coding: utf-8 -*-
# Part of Wicoders Solution. See LICENSE file for full copyright and licensing

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_advance_payment_purchase = fields.Boolean(string='Enable Advance Payment For Purchase')

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.default'].sudo().set('res.config.settings', 'enable_advance_payment_purchase', self.enable_advance_payment_purchase)
        return True

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        enable_advance_payment_purchase = self.env['ir.default']._get('res.config.settings', 'enable_advance_payment_purchase')
        res.update(enable_advance_payment_purchase=enable_advance_payment_purchase)
        return res

