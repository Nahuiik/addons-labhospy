# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Devintelle Software Solutions (<http://devintelle.com>).
#
##############################################################################

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    history_ids = fields.One2many('purchase.history', 'product_id', string='Purchase History')
    history_sale_ids = fields.One2many('sale.history', 'product_id', string='Sale History')
    edit_purchase_history = fields.Boolean(string="Edit History", compute="_compute_edit_history")

    @api.depends_context('uid')
    def _compute_edit_history(self):
        allow_edit_xmlid = 'gn_sale_and_purchase_history.allow_edit_purchase_history'
        can_edit = self.env.user.has_group(allow_edit_xmlid)
        for product in self:
            product.edit_purchase_history = can_edit

    #@api.multi
    #def _compute_sale_price(self):
    #    for rec in self:
    #        if rec.type == 'product' and rec.hospital_product_type in ['medicament', 'disposable_material','nutrition']:
    #            if rec.history_ids.filtered(lambda h: not h.exclude_from_sale_price):
    #                highest_price = max(rec.history_ids.filtered(lambda h: not h.exclude_from_sale_price).mapped('price'))
    #                rec.list_price = math.ceil(highest_price * 1.4)

    @api.constrains('default_code')
    def _check_default_code_unique(self):
        for record in self:
            if record.default_code:
                domain = [('default_code', '=', record.default_code)]
                if record.id:
                    domain.append(('id', '!=', record.id))
                if self.env['product.template'].search(domain, limit=1):
                    raise ValidationError(
                        _("La referencia interna '%s' ya existe.") % record.default_code
                    )
