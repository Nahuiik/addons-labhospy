# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models, _
from datetime import datetime
import calendar
from odoo.exceptions import ValidationError

MONTH = [('1', 'January'),
         ('2', 'February'),
         ('3', 'March'),
         ('4', 'April'),
         ('5', 'May'),
         ('6', 'June'),
         ('7', 'July'),
         ('8', 'August'),
         ('9', 'September'),
         ('10', 'October'),
         ('11', 'November'),
         ('12', 'December')]


class FacturasVentas(models.Model):
    _name = 'libro.ventas.invoice'
    _description = 'Facturas de Clientes'
    _order = 'numero_factura'

    treasury_id = fields.Many2one("libro.ventas.forecast", "Forecast")
    factura_id = fields.Integer("Id de factura")
    invoice_id = fields.Many2one("account.move", string="No. Documento")
    numero_factura = fields.Char("No. Factura")
    invoice_date = fields.Date("Fecha de Factura")
    date_due = fields.Date(string="Fecha de Vencimiento")
    partner_id = fields.Many2one("res.partner", string="Empresa")
    state = fields.Selection([('draft', 'Borrador'),
                              ('posted',  'Posted'),
                              ('cancel', 'Cancelled'),
                              ],
                             string="State")
    total_amount = fields.Float(string="Total de Factura",
                                digits=(12, 2))
    subtotal = fields.Float(string="SubTotal",
                            digits=(12, 2))
    tipo_factura = fields.Char("Tipo de Factura")
    isv = fields.Float(string="Impuesto",
                       digits=(12, 2), compute="_compute_amount_tax_15_per",)
    amount_tax_15_per = fields.Float(compute="_compute_amount_tax_15_per", string="Gravado")
    exempt_sale_amount = fields.Float(compute="_compute_amount_tax_15_per", string="Exento")
    exonerate_amount = fields.Float(compute="_compute_amount_tax_15_per", string="Exonerado")

    @api.depends(
        'invoice_id.invoice_line_ids.price_subtotal',
        'invoice_id.invoice_line_ids.price_total',
        'invoice_id.invoice_line_ids.tax_ids',
    )
    def _compute_amount_tax_15_per(self):
        for rec in self:
            if rec.invoice_id:
                amount_tax_15_per = 0
                exempt_sale_amount = 0
                exonerate_amount = 0
                taxes = 0
                for line in rec.invoice_id.invoice_line_ids:
                    if line.display_type:
                        continue
                    line_tax = line.price_total - line.price_subtotal
                    taxes += line_tax
                    for tax in line.tax_ids:
                        if tax.amount_type == 'percent' and tax.amount == 15:
                            amount_tax_15_per += line.price_subtotal
                            break
                    for tax in line.tax_ids:
                        if getattr(tax, 'is_exempt', False):
                            exempt_sale_amount += line.price_subtotal
                            break
                    for tax in line.tax_ids:
                        if getattr(tax, 'is_exonerate', False):
                            exonerate_amount += line.price_subtotal
                            break
                rec.amount_tax_15_per = amount_tax_15_per
                rec.exempt_sale_amount = exempt_sale_amount
                rec.exonerate_amount = exonerate_amount
                rec.isv = taxes

            else:
                rec.amount_tax_15_per = 0
                rec.exempt_sale_amount = 0
                rec.exonerate_amount = 0
                rec.isv = 0

class AccountTreasuryForecast(models.Model):
    _name = 'libro.ventas.forecast'
    _description = 'Libro de Ventas'
    _order = "id desc"

    def _get_year_selection(self):
        year = datetime.now().year - 9
        return [(str(year + r), str(year + r)) for r in range(10)]

    def _get_current_year(self):
        return str(datetime.now().year)

    def _get_current_selection(self):
        return str(datetime.now().month)

    def get_currency(self):
        return self.env.user.company_id.currency_id.id

    currency_id = fields.Many2one("res.currency", "Moneda", required=True,
                                  readonly=True, domain=[('active', '=', True)],
                                  default=get_currency)
    name = fields.Char(string="Descripción")
    # Borrar
    total_incoming = fields.Float(string="Total de Ventas", readonly=True)
    sub_total = fields.Float("Neto Gravado", readonly=True)
    total_gravado = fields.Float("Total Gravado", readonly=True)
    total_impuesto = fields.Float("Impuestos", readonly=True)
    total_exento = fields.Float(string="Total Facturas Exentas")
    total_exonerate = fields.Float(string="Total Facturas Exoneradas")
    # Borrar
    state = fields.Selection([('draft', 'Borrador'), ('progress', 'Progreso'),
                              ('done', 'Finalizado')], string='Estado',
                             default='draft')
    start_date = fields.Date(string="Fecha de Inicio", required=True)
    end_date = fields.Date(string="Fecha Final", required=True)
    check_draft = fields.Boolean(string="Borrador")
    check_open = fields.Boolean(string="Posted", default=1)
    check_cancel = fields.Boolean(string="Cancelled")
    facturas_gravadas = fields.Integer("# Facturas Gravadas")
    facturas_exentas = fields.Integer("# Facturas Exentas")
    facturas_exonerate = fields.Integer("# Facturas Exoneradas")
    total_numero_facturas = fields.Integer("# Facturas")
    out_invoice_ids = fields.One2many("libro.ventas.invoice", "treasury_id",
                                      "Facturas de Clientes")
    regimen = fields.Boolean("Facturas con Regimen", default=1)
    month = fields.Char(string="Month", compute="get_month", store=True)
    year = fields.Integer(string="Year", compute="get_month", store=True)
    cancel_count = fields.Integer(string="Cancelled Invoices")
    all_invoice = fields.Boolean(string="All Invoices")
    month_selection = fields.Selection(MONTH, string="Month (Selection)", default=_get_current_selection)
    year_selection = fields.Selection(_get_year_selection, string="Year (Selection)", default=_get_current_year)

    @api.onchange('month_selection', 'year_selection')
    def change_month_year(self):
        self.year = self.year_selection
        self.month = self.months(int(self.month_selection))
        if self.month_selection and self.year_selection:
            last_day = calendar.monthrange(int(self.year_selection), int(self.month_selection))[1]
            today = datetime.today()
            self.start_date = today.replace(month=int(self.month_selection), year=int(self.year_selection), day=1)
            self.end_date = today.replace(month=int(self.month_selection), year=int(self.year_selection), day=last_day)
            self.name = str(self.months(int(self.month_selection))) + " " + str(self.year_selection)

    @api.depends('start_date')
    def get_month(self):
        for sale in self:
            if sale.start_date:
                date = sale.start_date
                number_month = date.month
                sale.month = self.months(number_month)
                sale.year = date.year

    def months(self, number):
        if number == 1:
            return _('January')
        elif number == 2:
            return _('February')
        elif number == 3:
            return _('March')
        elif number == 4:
            return _('April')
        elif number == 5:
            return _('May')
        elif number == 6:
            return _('June')
        elif number == 7:
            return _('July')
        elif number == 8:
            return _('August')
        elif number == 9:
            return _('September')
        elif number == 10:
            return _('October')
        elif number == 11:
            return _('November')
        elif number == 12:
            return _('December')

    @api.constrains('end_date', 'start_date')
    def check_date(self):
        if self.start_date > self.end_date:
            raise ValidationError(_('Error!:: End date is lower than start date.'))

    @api.constrains('check_draft', 'check_cancel', 'check_open')
    def check_filter(self):
        if not self.check_draft and not self.check_cancel and \
                not self.check_open:
            raise ValidationError(
                _('Error!:: There is no any filter checked.'))

    def restart(self):
        self.out_invoice_ids.unlink()
        self.total_incoming = 0
        self.sub_total = 0
        self.total_impuesto = 0
        self.total_exento = 0
        self.total_exonerate = 0
        self.total_gravado = 0
        self.facturas_gravadas = 0
        self.facturas_exentas = 0
        self.facturas_exonerate = 0
        self.total_numero_facturas = 0
        return True

    def button_calculate(self):
        self.restart()
        self.calculate_invoices()
        self.calculate_total()
        self.action_progress()
        return True

    def calculate_total(self):
        if self.out_invoice_ids:
            amount = 0.0
            sub_total = 0.0
            isv = 0.0
            exento = 0.0
            exonerate = 0.0
            contador = 0.0
            contador_exento = 0.0
            contador_exonerado = 0.0
            cancel_count = 0
            total_gravado = 0
            amount_untaxed = 0
            for inv_line in self.out_invoice_ids:
                if inv_line.state != 'cancel':
                    amount += inv_line.total_amount
                    sub_total += inv_line.subtotal
                    exento += inv_line.exempt_sale_amount
                    exonerate += inv_line.exonerate_amount
                    total_gravado += inv_line.amount_tax_15_per
                    amount_untaxed += inv_line.subtotal
                    isv += inv_line.isv
                    # if inv_line.isv == 0:
                    #     exento += inv_line.subtotal
                    #     contador_exento += 1
                    # else:
                    #     sub_total += inv_line.subtotal
                    #     isv += inv_line.isv
                    #     contador += 1
                    # total_gravado += inv_line.subtotal
                else:
                    cancel_count += 1
                # total_impuest = isv
            for inv in self.out_invoice_ids.mapped('invoice_id'):
                if not inv.amount_tax:
                    tiene_exonerado = False
                    tiene_exento = False
                    for line in inv.invoice_line_ids:
                        # Recorre los impuestos asociados a cada línea
                        for tax in line.tax_ids:
                            if tax.is_exonerate:
                                tiene_exonerado = True
                            if tax.is_exempt:
                                tiene_exento = True

                    # Si alguna línea tiene impuesto exonerado, suma al contador
                    if tiene_exonerado:
                        contador_exonerado += 1

                    # Si alguna línea tiene impuesto exento, suma al contador
                    if tiene_exento:
                        contador_exento += 1
                else:
                    contador += 1
                # if inv.currency_id.id != inv.company_id.currency_id.id:
                #     total_impuest += inv.amount_tax_signed

                # else:
                #     total_impuest += inv.amount_tax
            self.total_incoming = amount

            self.cancel_count = cancel_count
            self.total_impuesto = isv


            self.total_gravado = total_gravado #Total Gravado (total of all invoice if have tax)
            self.sub_total = amount_untaxed  # Neto Gravado (total untax of all invoice)
            self.total_exento = exento #Total Facturas Exentas	(untax amount if invoice have no tax)
            self.total_exonerate = exonerate #Total Facturas Exentas	(untax amount if invoice have no tax)
            self.facturas_gravadas = contador
            self.facturas_exentas = contador_exento
            self.facturas_exonerate = contador_exonerado
            self.total_numero_facturas = len(self.out_invoice_ids)

    def calculate_invoices(self):
        invoice_obj = self.env['account.move']
        treasury_invoice_obj = self.env['libro.ventas.invoice']
        state = []
        invoice_ids = False
        self.total_incoming = 0
        if self.check_draft:
            state.append("draft")
        if self.check_open:
            state.append("posted")
        if self.check_cancel:
            state.append("cancel")


        invoice_ids = invoice_obj.search(
            [('invoice_date', '>=', self.start_date),
             ('invoice_date', '<=', self.end_date),
             ('state', 'in', tuple(state)),
             ('move_type', '=', 'out_invoice')
             ])
        amount1 = sum(invoice_ids.filtered(lambda i: i.amount_tax > 0.0).mapped('amount_untaxed'))
        amount2 = sum(invoice_ids.filtered(lambda i: i.amount_tax <= 0.0).mapped('amount_untaxed'))
        for invoice_o in invoice_ids:
            if not self.all_invoice:
                if self.regimen and invoice_o.cai_invoice:
                    values = {
                        'treasury_id': self.id,
                        'invoice_id': invoice_o.id,
                        'factura_id': invoice_o.id,
                        'date_due': invoice_o.invoice_date_due,
                        'numero_factura': invoice_o.name,
                        'invoice_date': invoice_o.invoice_date,
                        'partner_id': invoice_o.partner_id.id,
                        'state': invoice_o.state
                    }
                    if self.currency_id == invoice_o.currency_id:
                        if invoice_o.move_type == 'out_invoice':
                            self.total_incoming += invoice_o.amount_total
                        elif invoice_o.move_type == 'out_refund':
                            self.total_incoming -= invoice_o.amount_total
                        elif invoice_o.move_type in ("in_invoice", "in_refund"):
                            self.total_invoice_out += invoice_o.amount_total
                        values["subtotal"] = invoice_o.amount_untaxed
                        values['isv'] = invoice_o.amount_tax
                        values['total_amount'] = invoice_o.amount_total
                    else:
                        if invoice_o.move_type == 'out_invoice':
                            self.total_incoming += abs(invoice_o.amount_total_signed)
                        elif invoice_o.move_type == 'out_refund':
                            self.total_incoming -= abs(invoice_o.amount_total_signed)
                        elif invoice_o.move_type in ("in_invoice", "in_refund"):
                            self.total_invoice_out += abs(invoice_o.amount_total_signed)
                        values["subtotal"] =  invoice_o.amount_untaxed_signed
                        values['isv'] = invoice_o.amount_tax_signed
                        values['total_amount']  = abs(invoice_o.amount_total_signed)
                        
                    if invoice_o.amount_tax > 0:
                        values['tipo_factura'] = 'Gravada'
                    elif invoice_o.exonerate_amount > 0:
                        values['tipo_factura'] = 'Exonerada'
                    elif invoice_o.exempt_sale_amount > 0:
                        values['tipo_factura'] = 'Exenta'
                    else:
                        values['tipo_factura'] = ''
                    new_id = treasury_invoice_obj.create(values)

                if not self.regimen and not invoice_o.cai_invoice:
                    values = {
                        'treasury_id': self.id,
                        'invoice_id': invoice_o.id,
                        'factura_id': invoice_o.id,
                        'date_due': invoice_o.invoice_date_due,
                        'numero_factura': invoice_o.name,
                        'invoice_date': invoice_o.invoice_date,
                        'partner_id': invoice_o.partner_id.id,
                        'state': invoice_o.state
                    }
                    if self.currency_id == invoice_o.currency_id:
                        if invoice_o.move_type == 'out_invoice':
                            self.total_incoming += invoice_o.amount_total
                        elif invoice_o.move_type == 'out_refund':
                            self.total_incoming -= invoice_o.amount_total
                        elif invoice_o.move_type in ("in_invoice", "in_refund"):
                            self.total_invoice_out += invoice_o.amount_total
                        values["subtotal"] = invoice_o.amount_untaxed
                        values['isv'] = invoice_o.amount_tax
                        values['total_amount'] = invoice_o.amount_total
                    else:
                        if invoice_o.move_type == 'out_invoice':
                            self.total_incoming += abs(invoice_o.amount_total_signed)
                        elif invoice_o.move_type == 'out_refund':
                            self.total_incoming -= abs(invoice_o.amount_total_signed)
                        elif invoice_o.move_type in ("in_invoice", "in_refund"):
                            self.total_invoice_out += abs(invoice_o.amount_total_signed)
                        values["subtotal"] =  invoice_o.amount_untaxed_signed
                        values['isv'] = invoice_o.amount_tax_signed
                        values['total_amount']  = abs(invoice_o.amount_total_signed)
                        
                    if invoice_o.amount_tax > 0:
                        values['tipo_factura'] = 'Gravada'
                    elif invoice_o.exonerate_amount > 0:
                        values['tipo_factura'] = 'Exonerada'
                    elif invoice_o.exempt_sale_amount > 0:
                        values['tipo_factura'] = 'Exenta'
                    else:
                        values['tipo_factura'] = ''

                    new_id = treasury_invoice_obj.create(values)
            else:
                if invoice_o.cai_invoice:
                    values = {
                        'treasury_id': self.id,
                        'invoice_id': invoice_o.id,
                        'factura_id': invoice_o.id,
                        'date_due': invoice_o.invoice_date_due,
                        'numero_factura': invoice_o.name,
                        'invoice_date': invoice_o.invoice_date,
                        'partner_id': invoice_o.partner_id.id,
                        'state': invoice_o.state
                    }
                    if self.currency_id == invoice_o.currency_id:
                        if invoice_o.move_type == 'out_invoice':
                            self.total_incoming += invoice_o.amount_total
                        elif invoice_o.move_type == 'out_refund':
                            self.total_incoming -= invoice_o.amount_total
                        elif invoice_o.move_type in ("in_invoice", "in_refund"):
                            self.total_invoice_out += invoice_o.amount_total
                        values["subtotal"] = invoice_o.amount_untaxed
                        values['isv'] = invoice_o.amount_tax
                        values['total_amount'] = invoice_o.amount_total
                    else:
                        if invoice_o.move_type == 'out_invoice':
                            self.total_incoming += abs(invoice_o.amount_total_signed)
                        elif invoice_o.move_type == 'out_refund':
                            self.total_incoming -= abs(invoice_o.amount_total_signed)
                        elif invoice_o.move_type in ("in_invoice", "in_refund"):
                            self.total_invoice_out += abs(invoice_o.amount_total_signed)
                        values["subtotal"] =  invoice_o.amount_untaxed_signed
                        values['isv'] = invoice_o.amount_tax_signed
                        values['total_amount']  = abs(invoice_o.amount_total_signed)

                    if invoice_o.amount_tax > 0:
                        values['tipo_factura'] = 'Gravada'
                    elif invoice_o.exonerate_amount > 0:
                        values['tipo_factura'] = 'Exonerada'
                    elif invoice_o.exempt_sale_amount > 0:
                        values['tipo_factura'] = 'Exenta'
                    else:
                        values['tipo_factura'] = ''
                    new_id = treasury_invoice_obj.create(values)

                if not invoice_o.cai_invoice:
                    values = {
                        'treasury_id': self.id,
                        'invoice_id': invoice_o.id,
                        'factura_id': invoice_o.id,
                        'date_due': invoice_o.invoice_date_due,
                        'numero_factura': invoice_o.name,
                        'invoice_date': invoice_o.invoice_date,
                        'partner_id': invoice_o.partner_id.id,
                        'state': invoice_o.state
                    }
                    if self.currency_id == invoice_o.currency_id:
                        if invoice_o.move_type == 'out_invoice':
                            self.total_incoming += invoice_o.amount_total
                        elif invoice_o.move_type == 'out_refund':
                            self.total_incoming -= invoice_o.amount_total
                        elif invoice_o.move_type in ("in_invoice", "in_refund"):
                            self.total_invoice_out += invoice_o.amount_total
                        values["subtotal"] = invoice_o.amount_untaxed
                        values['isv'] = invoice_o.amount_tax
                        values['total_amount'] = invoice_o.amount_total
                    else:
                        if invoice_o.move_type == 'out_invoice':
                            self.total_incoming += abs(invoice_o.amount_total_signed)
                        elif invoice_o.move_type == 'out_refund':
                            self.total_incoming -= abs(invoice_o.amount_total_signed)
                        elif invoice_o.move_type in ("in_invoice", "in_refund"):
                            self.total_invoice_out += abs(invoice_o.amount_total_signed)
                        values["subtotal"] =  invoice_o.amount_untaxed_signed
                        values['isv'] = invoice_o.amount_tax_signed
                        values['total_amount']  = abs(invoice_o.amount_total_signed)
                    if invoice_o.amount_tax > 0:
                        values['tipo_factura'] = 'Gravada'
                    elif invoice_o.exonerate_amount > 0:
                        values['tipo_factura'] = 'Exonerada'
                    elif invoice_o.exempt_sale_amount > 0:
                        values['tipo_factura'] = 'Exenta'
                    else:
                        values['tipo_factura'] = ''

                    new_id = treasury_invoice_obj.create(values)

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_progress(self):
        self.write({'state': 'progress'})

    def action_done(self):
        self.write({'state': 'done'})
