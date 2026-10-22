# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    gn_sale_user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        related="sale_id.user_id",
        store=True,
        readonly=True,
    )
    gn_invoice_display = fields.Char(
        string="Factura",
        compute="_compute_gn_invoice_display",
        store=True,
    )

    @api.depends(
        "sale_id",
        "sale_id.invoice_ids",
        "sale_id.invoice_ids.name",
        "sale_id.invoice_ids.state",
        "sale_id.invoice_ids.move_type",
    )
    def _compute_gn_invoice_display(self):
        for picking in self:
            order = picking.sale_id
            if not order:
                picking.gn_invoice_display = False
                continue
            invoices = order.invoice_ids.filtered(
                lambda m: m.move_type == "out_invoice" and m.state == "posted"
            ).sorted("name")
            picking.gn_invoice_display = (
                ", ".join(invoices.mapped("name")) if invoices else False
            )
