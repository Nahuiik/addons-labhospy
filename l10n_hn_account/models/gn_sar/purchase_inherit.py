from odoo import models, fields, api, _


class purchase_order(models.Model):
    _inherit = 'purchase.order'

    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        change_default=True,
        tracking=True,
        index=True,
        check_company=True,
        domain="[('supplier', '=', True)]",
        help="You can find a vendor by its Name, TIN, Email or Internal Reference.",
    )
    vendor_invoice_number = fields.Char(string="Factura del proveedor")
    cai_shot_compras = fields.Char(
        string="CAI Compras",
        compute="_compute_cai_shot_compras",
        help="Vista previa del CAI (compatibilidad vistas; el CAI definitivo sigue en la factura proveedor).",
    )
    exempt_sale_amount = fields.Float(compute='_get_exempt_and_taxed_sales', string="Exempt Sale")
    taxed_sales = fields.Float(compute='_get_exempt_and_taxed_sales', string="Taxed Sales")
    exonerate_amount = fields.Float(compute='_get_exonerate_amount', string="Exonerate Amount")
    tax_15_per = fields.Float(compute='_get_tex_per_amount', string="Tax 15%")
    tax_18_per = fields.Float(compute='_get_tex_per_amount', string="Tax 18%")
    amount_tax_15_per = fields.Float(compute='_get_tex_per_amount', string="Taxed Amount 15%")
    amount_tax_18_per = fields.Float(compute='_get_tex_per_amount', string="Taxed Amount 18%")

    @api.depends(
        "partner_id",
        "partner_id.multiple_cais",
        "partner_id.cai_shot",
        "vendor_invoice_number",
        "date_order",
        "partner_id.supplier_cai_ids.supplier_prefix",
        "partner_id.supplier_cai_ids.supplier_cai_shot",
        "partner_id.supplier_cai_ids.supplier_cai_expires_shot",
        "partner_id.supplier_cai_ids.supplier_min_number_shot",
        "partner_id.supplier_cai_ids.supplier_max_number_shot",
    )
    def _compute_cai_shot_compras(self):
        for order in self:
            order.cai_shot_compras = order._l10n_hn_po_cai_preview()

    def _l10n_hn_po_cai_preview(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return ""
        if not partner.multiple_cais:
            return partner.cai_shot or ""
        vin = self.vendor_invoice_number or ""
        parts = vin.split("-")
        if len(parts) < 2:
            return partner.cai_shot or ""
        prefix_info = "-".join(parts[:-1])
        try:
            correlativo = int(parts[-1])
        except ValueError:
            return partner.cai_shot or ""
        cai_lines = partner.supplier_cai_ids.filtered(
            lambda c: c.supplier_prefix == prefix_info
        )
        if not cai_lines:
            return partner.cai_shot or ""
        order_day = self.date_order
        if order_day:
            order_day = fields.Date.to_date(order_day)
        else:
            order_day = fields.Date.today()
        for cai in cai_lines:
            exp = cai.supplier_cai_expires_shot
            if exp and exp < order_day:
                continue
            try:
                min_n = int(cai.supplier_min_number_shot)
                max_n = int(cai.supplier_max_number_shot)
            except (TypeError, ValueError):
                continue
            if min_n <= correlativo <= max_n:
                return cai.supplier_cai_shot or ""
        return partner.cai_shot or ""

    @api.depends(
        'order_line.tax_ids',
        'order_line.price_unit',
        'order_line.product_qty',
        'order_line.product_id',
        'order_line.display_type',
    )
    def _get_tex_per_amount(self):
        for rec in self:
            tax_15_per = 0
            tax_18_per = 0
            amount_tax_15_per = 0
            amount_tax_18_per = 0
            for line in rec.order_line:
                if line.display_type:
                    continue
                price = line.price_unit
                for tax in line.tax_ids:
                    if tax.amount_type == 'percent' and tax.amount == 15:
                        taxes = tax.compute_all(
                            price,
                            rec.currency_id,
                            line.product_qty,
                            product=line.product_id,
                            partner=rec.partner_id,
                        )
                        tax_15_per += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                        amount_tax_15_per += taxes.get('total_excluded')
                    if tax.amount_type == 'percent' and tax.amount == 18:
                        taxes = tax.compute_all(
                            price,
                            rec.currency_id,
                            line.product_qty,
                            product=line.product_id,
                            partner=rec.partner_id,
                        )
                        tax_18_per += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                        amount_tax_18_per += taxes.get('total_excluded')
            rec.tax_15_per = tax_15_per
            rec.tax_18_per = tax_18_per
            rec.amount_tax_15_per = amount_tax_15_per
            rec.amount_tax_18_per = amount_tax_18_per

    @api.depends(
        'order_line.tax_ids',
        'order_line.price_unit',
        'order_line.product_qty',
        'order_line.display_type',
        'partner_id',
    )
    def _get_exonerate_amount(self):
        for rec in self:
            exonerate_amount = 0
            if rec.partner_id.is_exonerated:
                for line in rec.order_line:
                    if line.display_type:
                        continue
                    price_total = line.price_unit * line.product_qty
                    if any(tax.is_exonerate for tax in line.tax_ids):
                        exonerate_amount += price_total
            rec.exonerate_amount = exonerate_amount

    @api.depends(
        'order_line.tax_ids',
        'order_line.price_unit',
        'order_line.product_qty',
        'order_line.display_type',
    )
    def _get_exempt_and_taxed_sales(self):
        for rec in self:
            exempt_sale_amount = 0
            taxed_sales = 0
            for line in rec.order_line:
                if line.display_type:
                    continue
                price_total = line.price_unit * line.product_qty
                taxes = line.tax_ids
                if any(tax.amount > 0 for tax in taxes):
                    taxed_sales += price_total
                if any(tax.is_exempt for tax in taxes):
                    exempt_sale_amount += price_total
            rec.exempt_sale_amount = exempt_sale_amount
            rec.taxed_sales = taxed_sales

    def _prepare_invoice(self):
        """Propagate vendor invoice number to the created bill."""
        self.ensure_one()
        res = super()._prepare_invoice()
        res["supplier_invoice_number"] = self.vendor_invoice_number or False
        res["cai_shot_compras"] = self.cai_shot_compras or False
        return res

    def _create_invoices(self, grouped=False, final=False):
        invoices = super()._create_invoices(grouped=grouped, final=final)
        for order in self:
            if not order.vendor_invoice_number:
                continue
            related = invoices.filtered(
                lambda move, order=order: move.invoice_origin == order.name
                and move.move_type in ("in_invoice", "in_refund", "in_receipt")
            )
            if related:
                related.write({"supplier_invoice_number": order.vendor_invoice_number})
        return invoices
