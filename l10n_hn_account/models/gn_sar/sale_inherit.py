from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        change_default=True,
        index=True,
        tracking=1,
        check_company=True,
        domain="[('customer', '=', True)]",
    )
    exempt_sale_amount = fields.Float(compute='_get_exempt_and_taxed_sales', string="Exempt Sale")
    taxed_sales = fields.Float(compute='_get_exempt_and_taxed_sales', string="Taxed Sales")
    exonerate_amount = fields.Float(compute='_get_exonerate_amount', string="Exonerate Amount")
    tax_15_per = fields.Float(compute='_get_tex_per_amount', string="Tax 15%")
    tax_18_per = fields.Float(compute='_get_tex_per_amount', string="Tax 18%")
    amount_tax_15_per = fields.Float(compute='_get_tex_per_amount', string="Taxed Amount 15%")
    amount_tax_18_per = fields.Float(compute='_get_tex_per_amount', string="Taxed Amount 18%")
    custom_invoice_id = fields.Many2one(
        'account.move',
        string="Invoice",
        compute='_get_custom_invoice',
        store=True,
    )

    @api.depends('order_line', 'invoice_ids', 'invoice_ids.state', 'invoice_ids.invoice_date')
    def _get_custom_invoice(self):
        for rec in self:
            invoice_ids = rec.invoice_ids.filtered(lambda i: i.state not in ('draft', 'cancel'))
            if invoice_ids:
                rec.custom_invoice_id = invoice_ids.sorted('invoice_date', reverse=True)[:1]
            else:
                rec.custom_invoice_id = False

    @api.depends('order_line')
    def _get_tex_per_amount(self):
        for rec in self:
            tax_15_per = 0
            tax_18_per = 0
            amount_tax_15_per = 0
            amount_tax_18_per = 0
            for line in rec.order_line:
                price = (line.price_unit * (1 - (line.discount or 0.0) / 100.0))

                for tax in line.tax_ids:
                    if tax.amount_type == 'percent' and tax.amount == 15:
                        taxes = tax.compute_all(price, line.order_id.currency_id,
                                                line.product_uom_qty,
                                                partner=line.order_id.partner_id)
                        tax_15_per += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                        amount_tax_15_per += taxes.get('total_excluded')
                    if tax.amount_type == 'percent' and tax.amount == 18:
                        taxes = tax.compute_all(price, line.order_id.currency_id,
                                                line.product_uom_qty,
                                                partner=line.order_id.partner_id)
                        tax_18_per += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                        amount_tax_18_per += taxes.get('total_excluded')
            rec.tax_15_per = tax_15_per
            rec.tax_18_per = tax_18_per 
            rec.amount_tax_15_per  = amount_tax_15_per 
            rec.amount_tax_18_per = amount_tax_18_per   

    @api.depends('order_line')                 
    def _get_exonerate_amount(self):
        for rec in self:
            exonerate_amount = 0
            if self.partner_id.is_exonerated:
                for line in rec.order_line:
                        price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                        for tax in line.tax_ids:
                            if tax.is_exonerate:
                                exonerate_amount += price * line.product_uom_qty
            rec.exonerate_amount = exonerate_amount
    
    @api.depends('order_line')
    def _get_exempt_and_taxed_sales(self):
        for rec in self:
            exempt_sale_amount = 0
            taxed_sales = 0
            for line in rec.order_line:
                price = (line.price_unit * (1 - (line.discount or 0.0) / 100.0))
                for tax in line.tax_ids:
                    if tax.amount > 0:
                        taxed_sales += price * line.product_uom_qty
                    if tax.is_exempt:
                        exempt_sale_amount += price * line.product_uom_qty
                
        rec.exempt_sale_amount = exempt_sale_amount
        rec.taxed_sales = taxed_sales
