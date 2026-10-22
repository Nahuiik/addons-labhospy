# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    is_imported_line = fields.Boolean(
        string='Línea importada',
        default=False,
        help='Indica si la línea fue creada por el asistente de importación.',
    )
