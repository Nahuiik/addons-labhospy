# -*- coding: utf-8 -*-
# Email: sales@creyox.com

from odoo import models, fields, api, _


class IrConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    sale_merge_duplicate_line = fields.Boolean(
        related='company_id.sale_merge_duplicate_line', string='Merge Duplicate Line in Sale', readonly=False)


class ResCompany(models.Model):
    _inherit = 'res.company'

    sale_merge_duplicate_line = fields.Boolean('Merge Duplicate Line in Sale')
