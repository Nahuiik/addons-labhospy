# -*- coding: utf-8 -*-

from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Factura',
        compute='_compute_invoice_id',
        store=True,
        readonly=True,
        help='Factura asociada a la cotización'
    )
    
    @api.depends('invoice_ids', 'invoice_ids.state', 'invoice_ids.move_type', 'invoice_ids.create_date', 'invoice_ids.name')
    def _compute_invoice_id(self):
        """Calcula la factura principal asociada a la orden de venta"""
        for order in self:
            invoice = False
            # Solo calcular si hay invoice_ids, la orden tiene un ID y no estamos en proceso de creación
            try:
                if order.invoice_ids and order.id:
                    # Filtrar facturas de cliente (out_invoice) que no estén canceladas
                    valid_invoices = order.invoice_ids.filtered(
                        lambda inv: inv.move_type == 'out_invoice' and inv.state not in ('cancel', 'draft')
                    )
                    if valid_invoices:
                        # Tomar la factura más reciente por fecha de creación
                        invoice = valid_invoices.sorted('create_date', reverse=True)[0]
                    elif order.invoice_ids:
                        # Si no hay facturas válidas, tomar la primera disponible que no esté cancelada
                        available_invoices = order.invoice_ids.filtered(
                            lambda inv: inv.state != 'cancel'
                        )
                        if available_invoices:
                            invoice = available_invoices.sorted('create_date', reverse=True)[0]
            except Exception:
                # Si hay cualquier error, simplemente no asignar factura para no interferir
                invoice = False
            order.invoice_id = invoice
    

