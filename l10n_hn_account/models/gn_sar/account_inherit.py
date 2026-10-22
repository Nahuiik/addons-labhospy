from lxml import etree

from odoo import models, fields, api, _


class account_move(models.Model):
    _inherit = "account.move"
    
    exempt_sale_amount = fields.Float(compute='_get_exempt_and_taxed_sales', string="Venta Exenta", help="Exempt Sale")
    taxed_sales = fields.Float(compute='_get_exempt_and_taxed_sales', string="Venta Gravada", help="Taxed Sales")
    exempt_purchase_no = fields.Char(string="Nº Order No. Exempt Purchase")
    reg_of_sag = fields.Char(string="Nº Registration of the SAG")
    constancy_exonerated_record = fields.Char(string="N° Constancy Exonerated Record")
    
    exonerate_amount = fields.Float(compute='_get_exonerate_amount', string="Exonerate Amount")
    tax_15_per = fields.Float(compute='_get_tex_per_amount', string="Tax 15%")
    tax_18_per = fields.Float(compute='_get_tex_per_amount', string="Tax 18%")
    amount_tax_15_per = fields.Float(compute='_get_tex_per_amount', string="Taxed Amount 15%")
    amount_tax_18_per = fields.Float(compute='_get_tex_per_amount', string="Taxed Amount 18%")
    is_customer_invoice = fields.Boolean(compute='_check_invoice_type', store=True)
    is_vendor_invoice = fields.Boolean(compute='_check_invoice_type', store=True)

    _customer_move_types = ('out_invoice', 'out_refund', 'out_receipt')
    _supplier_move_types = ('in_invoice', 'in_refund', 'in_receipt')

    @api.depends('move_type')
    def _check_invoice_type(self):
        for rec in self:
            if rec.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                rec.is_customer_invoice = True
                rec.is_vendor_invoice = False
            elif rec.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
                rec.is_customer_invoice = False
                rec.is_vendor_invoice = True
            else:
                rec.is_customer_invoice = False
                rec.is_vendor_invoice = False

    def print_customer_receipt(self):
        return self.env.ref('l10n_hn_account.action_customer_receipt').report_action(self)
    
    @api.depends('invoice_line_ids')
    def _get_tex_per_amount(self):
        for rec in self:
            tax_15_per = 0
            tax_18_per = 0
            amount_tax_15_per = 0
            amount_tax_18_per = 0
            for line in rec.invoice_line_ids:
                price = (line.price_unit * (1 - (line.discount or 0.0) / 100.0))
#                 price = price * line.quantity
                for tax in line.tax_ids:
                    if tax.amount_type == 'percent' and tax.amount == 15:
                        taxes = tax.compute_all(price, line.move_id.currency_id,
                                                        line.quantity,
                                                        partner=line.move_id.partner_id)
                        tax_15_per += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                        amount_tax_15_per += taxes.get('total_excluded')
                    if tax.amount_type == 'percent' and tax.amount == 18:
                        taxes = tax.compute_all(price, line.move_id.currency_id,
                                                        line.quantity,
                                                        partner=line.move_id.partner_id)
                        tax_18_per += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                        #tax_18_per += (price * 18) / 100
                        amount_tax_18_per += taxes.get('total_excluded')
            rec.tax_15_per = tax_15_per
            rec.tax_18_per = tax_18_per     
            rec.amount_tax_15_per = amount_tax_15_per
            rec. amount_tax_18_per = amount_tax_18_per
                       
    @api.depends('invoice_line_ids')
    def _get_exonerate_amount(self):
        for rec in self:
            exonerate_amount = 0
            if rec.partner_id.is_exonerated:
                for line in rec.invoice_line_ids:
                        price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                        for tax in line.tax_ids:
                            if tax.is_exonerate:
                                exonerate_amount += price * line.quantity
            rec.exonerate_amount = exonerate_amount
    
    @api.depends('invoice_line_ids')
    def _get_exempt_and_taxed_sales(self):
        for rec in self:
            exempt_sale_amount = 0
            taxed_sales = 0
            for line in rec.invoice_line_ids:
                for tax in line.tax_ids:
                    if tax.amount > 0:
                        taxed_sales += line.price_subtotal
                    if tax.is_exempt:
                        exempt_sale_amount += line.price_subtotal
                
            rec.exempt_sale_amount = exempt_sale_amount
            rec.taxed_sales = taxed_sales

    def _get_partner_role_from_context(self):
        ctx = self.env.context
        role = ctx.get('res_partner_search_mode')
        if role in ('customer', 'supplier'):
            return role

        move_type = ctx.get('default_move_type')
        if not move_type and ctx.get('active_model') == 'account.move':
            active_ids = ctx.get('active_ids') or [ctx.get('active_id')]
            active_ids = [aid for aid in active_ids if aid]
            if active_ids:
                move = self.env['account.move'].browse(active_ids[0])
                if move.exists():
                    move_type = move.move_type
        if move_type in self._customer_move_types:
            return 'customer'
        if move_type in self._supplier_move_types:
            return 'supplier'

        hints = {
            'search_default_out_invoice': 'customer',
            'search_default_out_refund': 'customer',
            'search_default_out_receipt': 'customer',
            'search_default_in_invoice': 'supplier',
            'search_default_in_refund': 'supplier',
            'search_default_in_receipt': 'supplier',
        }
        for key, value in hints.items():
            if ctx.get(key):
                return value
        return None

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type != 'form':
            return res

        partner_role = self._get_partner_role_from_context()
        if not partner_role:
            return res

        domain_map = {
            'customer': "['&', ('company_id', 'in', (False, company_id)), ('is_customer', '=', True)]",
            'supplier': "['&', ('company_id', 'in', (False, company_id)), ('is_supplier', '=', True)]",
        }
        domain_str = domain_map.get(partner_role)
        if not domain_str:
            return res

        context_map = {
            'customer': "{'res_partner_search_mode': 'customer', 'show_address': 1, 'default_is_company': True, 'show_vat': True, 'default_customer_rank': 1, 'default_customer': True, 'default_is_customer': True}",
            'supplier': "{'res_partner_search_mode': 'supplier', 'show_address': 1, 'default_is_company': True, 'show_vat': True, 'default_supplier_rank': 1, 'default_supplier': True, 'default_is_supplier': True}",
        }
        context_str = context_map.get(partner_role)

        try:
            arch = etree.fromstring(res['arch'])
        except (etree.XMLSyntaxError, TypeError):
            return res

        updated = False
        xpath_expr = "//field[@name='partner_id' and (@widget='res_partner_many2one' or contains(@context, 'res_partner_search_mode'))]"
        nodes = arch.xpath(xpath_expr)
        if not nodes:
            nodes = arch.xpath("//field[@name='partner_id' and @widget='res_partner_many2one']")
        for field in nodes:
            field.set('domain', domain_str)
            if context_str:
                field.set('context', context_str)
            updated = True

        if updated:
            res['arch'] = etree.tostring(arch, encoding='unicode')
        return res
    
