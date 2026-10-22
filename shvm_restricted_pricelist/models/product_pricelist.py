# -*- coding: utf-8 -*-
# Email: sales@creyox.com

from odoo import models, fields, api, _


class ProductPriceList(models.Model):
    _inherit = 'product.pricelist'

    user_ids = fields.Many2many('res.users')
