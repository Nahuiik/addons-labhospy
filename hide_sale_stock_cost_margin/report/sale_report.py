# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    margin = fields.Float()
