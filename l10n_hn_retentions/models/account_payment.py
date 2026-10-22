from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError,ValidationError
from odoo.tools import format_date


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    apply_retentions = fields.Boolean(string='Apply Retentions')
    retention_sequence_id = fields.Char(string='Retention')
    retention_sequence_ids = fields.Many2one(comodel_name='ir.sequence', string='Sequence')
    
    apply_1 = fields.Boolean(string='Apply 1%')
    apply_12_5 = fields.Boolean(string='Apply 12.5%')
    apply_15 = fields.Boolean(string='Apply 15%')
    available_partner_bank_ids = fields.Many2many(
        comodel_name='res.partner.bank',
        compute='_compute_available_partner_bank_ids',
    )
    show_retention_option = fields.Boolean(string='Show Retention Option', compute='_compute_show_retention_visibility')
    show_retention_1 = fields.Boolean(string='Show Retention 1%', compute='_compute_show_retention_visibility')
    show_retention_12_5 = fields.Boolean(string='Show Retention 12.5%', compute='_compute_show_retention_visibility')
    show_retention_15 = fields.Boolean(string='Show Retention 15%', compute='_compute_show_retention_visibility')

    @staticmethod
    def _get_config_param(params, suffix, default='False'):
        new_key = f'l10n_hn_retentions.{suffix}'
        legacy_key = f'l10n_hn_gn_retentions.{suffix}'
        value = params.get_param(new_key)
        if value in (None, False, ''):
            value = params.get_param(legacy_key, default)
        return default if value in (None, False, '') else value

    @api.depends('payment_type', 'company_id')
    def _compute_show_retention_visibility(self):
        params = self.env['ir.config_parameter'].sudo()
        for payment in self:
            supplier_flow = payment.payment_type == 'outbound'
            customer_flow = payment.payment_type == 'inbound'

            if supplier_flow:
                option_enabled = tools.str2bool(
                    self._get_config_param(params, 'apply_retentions')
                )
                show_1 = tools.str2bool(
                    self._get_config_param(params, 'apply_1')
                )
                show_12 = tools.str2bool(
                    self._get_config_param(params, 'apply_12_5')
                )
                show_15 = tools.str2bool(
                    self._get_config_param(params, 'apply_15')
                )
            elif customer_flow:
                option_enabled = tools.str2bool(
                    self._get_config_param(params, 'apply_customer_retentions')
                )
                show_1 = tools.str2bool(
                    self._get_config_param(params, 'apply_customer_1')
                )
                show_12 = tools.str2bool(
                    self._get_config_param(params, 'apply_customer_12_5')
                )
                show_15 = tools.str2bool(
                    self._get_config_param(params, 'apply_customer_15')
                )
            else:
                option_enabled = False
                show_1 = False
                show_12 = False
                show_15 = False

            payment.show_retention_option = option_enabled
            payment.show_retention_1 = option_enabled and show_1
            payment.show_retention_12_5 = option_enabled and show_12
            payment.show_retention_15 = option_enabled and show_15

    def _sanitize_retention_flags(self):
        """Alinea flags de retención con la configuración visible (solo borrador)."""
        for payment in self.filtered(lambda p: p.state in (False, 'draft')):
            vals = {}
            if not payment.show_retention_option:
                for field in ('apply_retentions', 'apply_1', 'apply_12_5', 'apply_15'):
                    if payment[field]:
                        vals[field] = False
            else:
                if not payment.show_retention_1 and payment.apply_1:
                    vals['apply_1'] = False
                if not payment.show_retention_12_5 and payment.apply_12_5:
                    vals['apply_12_5'] = False
                if not payment.show_retention_15 and payment.apply_15:
                    vals['apply_15'] = False
            if vals:
                payment.with_context(skip_retention_sanitize=True).write(vals)

    @api.onchange('payment_type', 'company_id')
    def _onchange_payment_type_company_retention_flags(self):
        for rec in self:
            if not rec.show_retention_option:
                rec.apply_retentions = False
                rec.apply_1 = False
                rec.apply_12_5 = False
                rec.apply_15 = False
            else:
                if not rec.show_retention_1:
                    rec.apply_1 = False
                if not rec.show_retention_12_5:
                    rec.apply_12_5 = False
                if not rec.show_retention_15:
                    rec.apply_15 = False

    @api.onchange('apply_retentions')
    def changed_retention_sequence(self):
        for rec in self:
            if not rec.show_retention_option:
                rec.apply_retentions = False
                continue
            sequence=self.env.ref('l10n_hn_retentions.seq_retentions_supplier').id
            rec.retention_sequence_ids = sequence

    def _prepare_move_withholding_lines(self, default_values):
        """Incluir líneas de retención en el asiento del pago."""
        self.ensure_one()
        if not getattr(self, 'apply_retentions', False) or not self.invoice_lines:
            return super()._prepare_move_withholding_lines(default_values)

        retention_1 = sum((l.amount_retention_1 or 0) for l in self.invoice_lines)
        retention_12_5 = sum((l.amount_retention_12_5 or 0) for l in self.invoice_lines)
        retention_15 = sum((l.amount_retention_15 or 0) for l in self.invoice_lines)
        if not (retention_1 or retention_12_5 or retention_15):
            return super()._prepare_move_withholding_lines(default_values)

        def _tag_vals(line_vals, xmlid_suffix):
            tag = self.env.ref(
                'l10n_hn_retentions.hn_ret_tag_%s' % xmlid_suffix,
                raise_if_not_found=False,
            )
            if tag:
                line_vals['tax_tag_ids'] = [(6, 0, tag.ids)]
            return line_vals

        ICPSudo = self.env['ir.config_parameter'].sudo()
        line_name = default_values.get('name', '') or 'Manual Payment'
        lines = []
        branch_id = getattr(self, 'branch_id', None) and self.branch_id.id

        if self.apply_1 and retention_1:
            account_id = self._get_config_param(ICPSudo, 'account_ret_1' if self.payment_type == 'outbound' else 'account_customer_ret_1', '')
            if account_id:
                amount_currency = -retention_1 if self.payment_type == 'outbound' else retention_1
                balance = self.currency_id._convert(amount_currency, self.company_id.currency_id, self.company_id, self.date)
                line_vals = {
                    'name': _('Retención 1%'),
                    'date_maturity': self.date,
                    'partner_id': self.partner_id.id,
                    'account_id': int(account_id),
                    'currency_id': self.currency_id.id,
                    'amount_currency': amount_currency,
                    'balance': balance,
                }
                if branch_id:
                    line_vals['branch_id'] = branch_id
                lines.append(_tag_vals(line_vals, '1'))

        if self.apply_12_5 and retention_12_5:
            account_id = self._get_config_param(ICPSudo, 'account_ret_12_5' if self.payment_type == 'outbound' else 'account_customer_ret_12_5', '')
            if account_id:
                amount_currency = -retention_12_5 if self.payment_type == 'outbound' else retention_12_5
                balance = self.currency_id._convert(amount_currency, self.company_id.currency_id, self.company_id, self.date)
                line_vals = {
                    'name': _('Retención 12.5%'),
                    'date_maturity': self.date,
                    'partner_id': self.partner_id.id,
                    'account_id': int(account_id),
                    'currency_id': self.currency_id.id,
                    'amount_currency': amount_currency,
                    'balance': balance,
                }
                if branch_id:
                    line_vals['branch_id'] = branch_id
                lines.append(_tag_vals(line_vals, '12_5'))

        if self.apply_15 and retention_15:
            account_id = self._get_config_param(ICPSudo, 'account_ret_15' if self.payment_type == 'outbound' else 'account_customer_ret_15', '')
            if account_id:
                amount_currency = -retention_15 if self.payment_type == 'outbound' else retention_15
                balance = self.currency_id._convert(amount_currency, self.company_id.currency_id, self.company_id, self.date)
                line_vals = {
                    'name': _('Retención 15%'),
                    'date_maturity': self.date,
                    'partner_id': self.partner_id.id,
                    'account_id': int(account_id),
                    'currency_id': self.currency_id.id,
                    'amount_currency': amount_currency,
                    'balance': balance,
                }
                if branch_id:
                    line_vals['branch_id'] = branch_id
                lines.append(_tag_vals(line_vals, '15'))

        return lines if lines else super()._prepare_move_withholding_lines(default_values)

    @api.onchange('apply_1', 'apply_12_5', 'apply_15')
    def changed_apply_1_or_apply_12_5(self):
        for rec in self:
            if not rec.show_retention_option:
                rec.apply_retentions = False
                rec.apply_1 = False
                rec.apply_12_5 = False
                rec.apply_15 = False
                continue
            if not rec.show_retention_1:
                rec.apply_1 = False
            if not rec.show_retention_12_5:
                rec.apply_12_5 = False
            if not rec.show_retention_15:
                rec.apply_15 = False
            for line in rec.invoice_lines:
                if not line.invoice_id:
                    continue
                inv = line.invoice_id
                ret_1 = inv.ret_amount_1 if rec.apply_1 else 0.0
                ret_12_5 = inv.ret_amount_12_5 if rec.apply_12_5 else 0.0
                ret_15 = inv.ret_amount_15 if rec.apply_15 else 0.0
                total_ret = ret_1 + ret_12_5 + ret_15
                amount_net = inv.amount_residual - total_ret
                line.amount_retention_1 = ret_1
                line.amount_retention_12_5 = ret_12_5
                line.amount_retention_15 = ret_15
                line.amount = 0.0 if amount_net < 0 else amount_net

    @api.onchange('amount')
    def onchange_amount(self):
        """Reparte el importe entre facturas respetando la retención por línea.

        El 'Importe' es el efectivo neto que sale de banco. Por cada factura lo
        conciliado es (amount + retención) = residual, por lo que el tope de
        'amount' por línea es (residual - retención), NO el residual completo.
        La versión base (gts_multiple_invoice_payment_currency) usaba el residual
        completo e ignoraba la retención, dejando amount = residual y disparando
        la validación "Amount to pay can not be greater than Amount Due" al
        pagar una o varias facturas con retención desde el formulario de pago.
        """
        if self.amount and self.amount > 0 and self.invoice_lines:
            total_amount = self.amount
            for line in self.invoice_lines:
                line_ret = (
                    (line.amount_retention_1 or 0.0)
                    + (line.amount_retention_12_5 or 0.0)
                    + (line.amount_retention_15 or 0.0)
                )
                max_net = line.residual - line_ret
                if max_net < 0:
                    max_net = 0.0
                if total_amount > 0:
                    conv_amount = self.currency_id._convert(
                        total_amount, line.currency_id, self.env.user.company_id,
                        self.date, round=False)
                    if max_net < conv_amount:
                        line.amount = max_net
                        if line.currency_id.id == self.currency_id.id:
                            total_amount -= max_net
                        else:
                            spend_amount = line.currency_id._convert(
                                max_net, self.currency_id, self.company_id,
                                self.date, round=False)
                            total_amount -= spend_amount
                    else:
                        line.amount = self.currency_id._convert(
                            total_amount, line.currency_id, self.env.user.company_id,
                            self.date, round=False)
                        total_amount = 0
                else:
                    line.amount = 0.0
        elif self.amount is not None and self.amount <= 0:
            for line in self.invoice_lines:
                line.amount = 0.0

    def action_post(self):
        """Las líneas de retención se generan vía _prepare_move_withholding_lines."""
        return super(AccountPayment, self).action_post()
    def print_retention(self):
        report = self.env['ir.actions.report'].search([
            ('report_name', '=', 'l10n_hn_retentions.retention_print_view'),
            ('model', '=', 'account.payment'),
        ], limit=1)
        if not report:
            report = self.env.ref('l10n_hn_retentions.actions_report_retentions_xls', raise_if_not_found=False)
        if not report:
            paperformat = self.env.ref('l10n_hn_retentions.paperformat_retentions_new', raise_if_not_found=False)
            report = self.env['ir.actions.report'].create({
                'name': 'Comprobante de retención',
                'model': 'account.payment',
                'report_type': 'qweb-pdf',
                'report_name': 'l10n_hn_retentions.retention_print_view',
                'report_file': 'l10n_hn_retentions.retention_print_view',
                'paperformat_id': paperformat.id if paperformat else False,
            })
        return report.report_action(self)

    def l10n_hn_retention_invoice_cais(self):
        """CAIs únicos de las facturas del pago (sin repetir el mismo valor)."""
        self.ensure_one()
        seen = set()
        cais = []
        for line in self.invoice_lines:
            invoice = line.invoice_id
            if not invoice:
                continue
            cai = (
                getattr(invoice, 'cai_shot_compras', False) or invoice.cai_invoice or ''
            ).strip()
            if not cai:
                continue
            cai_key = cai.lower()
            if cai_key in seen:
                continue
            seen.add(cai_key)
            cais.append(cai)
        return cais

    def l10n_hn_retention_cai_expiry_label(self, invoice):
        """Texto de fecha límite de emisión del CAI para el reporte de retención.

        Si el proveedor acepta múltiples CAI, busca en ``supplier_cai_ids`` la fila cuyo
        CAI coincide con el del comprobante (``cai_shot_compras`` o ``cai_invoice``).
        Si no, o no hay coincidencia, usa la fecha de la factura o la del contacto.
        """
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return ''
        if not invoice:
            d = partner.cai_expires_shot
            return format_date(self.env, d) if d else ''
        doc_cai = (
            (getattr(invoice, 'cai_shot_compras', False) or invoice.cai_invoice or '')
        ).strip()
        doc_cai_key = doc_cai.lower() if doc_cai else ''
        exp = False
        if partner.multiple_cais and doc_cai_key:
            for sc in partner.supplier_cai_ids:
                if (sc.supplier_cai_shot or '').strip().lower() == doc_cai_key:
                    exp = sc.supplier_cai_expires_shot
                    break
        if not exp:
            exp = invoice.cai_expires_shot or partner.cai_expires_shot
        return format_date(self.env, exp) if exp else ''

    def l10n_hn_retention_invoice_cai_expiry_labels(self):
        """Fechas límite de emisión únicas de las facturas del pago (sin repetir)."""
        self.ensure_one()
        seen = set()
        labels = []
        for line in self.invoice_lines:
            label = self.l10n_hn_retention_cai_expiry_label(line.invoice_id)
            if not label or label in seen:
                continue
            seen.add(label)
            labels.append(label)
        return labels

    @api.depends('partner_id', 'company_id', 'payment_type')
    def _compute_available_partner_bank_ids(self):
        for pay in self:
            if pay.payment_type == 'inbound':
                pay.available_partner_bank_ids = pay.journal_id.bank_account_id
            else:
                pay.available_partner_bank_ids = pay.partner_id.bank_ids\
                        .filtered(lambda x: x.company_id.id in (False, pay.company_id.id))._origin

    @api.model_create_multi
    def create(self, vals_list):
        payments = super(AccountPayment, self).create(vals_list)
        payments._sanitize_retention_flags()
        return payments

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)
        if not self.env.context.get('skip_retention_sanitize') and {'payment_type', 'company_id'} & set(vals.keys()):
            self._sanitize_retention_flags()
        return res
    
    def to_word(self, number, mi_moneda):
        valor = number
        number = int(number)
        centavos = int((round(valor - number, 2)) * 100)
        UNIDADES = (
            '',
            'UN ',
            'DOS ',
            'TRES ',
            'CUATRO ',
            'CINCO ',
            'SEIS ',
            'SIETE ',
            'OCHO ',
            'NUEVE ',
            'DIEZ ',
            'ONCE ',
            'DOCE ',
            'TRECE ',
            'CATORCE ',
            'QUINCE ',
            'DIECISEIS ',
            'DIECISIETE ',
            'DIECIOCHO ',
            'DIECINUEVE ',
            'VEINTE '
        )

        DECENAS = (
            'VENTI',
            'TREINTA ',
            'CUARENTA ',
            'CINCUENTA ',
            'SESENTA ',
            'SETENTA ',
            'OCHENTA ',
            'NOVENTA ',
            'CIEN ')

        CENTENAS = (
            'CIENTO ',
            'DOSCIENTOS ',
            'TRESCIENTOS ',
            'CUATROCIENTOS ',
            'QUINIENTOS ',
            'SEISCIENTOS ',
            'SETECIENTOS ',
            'OCHOCIENTOS ',
            'NOVECIENTOS '
        )
        MONEDAS = (
            {'country': u'Colombia', 'currency': 'COP', 'singular': u'PESO COLOMBIANO', 'plural': u'PESOS COLOMBIANOS',
             'symbol': u'$'},
            {'country': u'Honduras', 'currency': 'HNL', 'singular': u'Lempira', 'plural': u'Lempiras', 'symbol': u'L'},
            {'country': u'Estados Unidos', 'currency': 'USD', 'singular': u'DÓLAR', 'plural': u'DÓLARES',
             'symbol': u'US$'},
            {'country': u'Europa', 'currency': 'EUR', 'singular': u'EURO', 'plural': u'EUROS', 'symbol': u'€'},
            {'country': u'México', 'currency': 'MXN', 'singular': u'PESO MEXICANO', 'plural': u'PESOS MEXICANOS',
             'symbol': u'$'},
            {'country': u'Perú', 'currency': 'PEN', 'singular': u'NUEVO SOL', 'plural': u'NUEVOS SOLES',
             'symbol': u'S/.'},
            {'country': u'Reino Unido', 'currency': 'GBP', 'singular': u'LIBRA', 'plural': u'LIBRAS', 'symbol': u'£'}
        )
        if mi_moneda != None:
            try:
                moneda = list(filter(lambda x: x['currency'] == mi_moneda, MONEDAS))
                moneda = moneda[0]
                if number < 2:
                    moneda = moneda['singular']
                else:
                    moneda = moneda['plural']
            except:
                return "Tipo de moneda inválida"
        else:
            moneda = ""
        converted = ''
        if not (0 < number < 999999999):
            return 'No es posible convertir el numero a letras'

        number_str = str(number).zfill(9)
        millones = number_str[:3]
        miles = number_str[3:6]
        cientos = number_str[6:]

        if (millones):
            if (millones == '001'):
                converted += 'UN MILLON '
            elif (int(millones) > 0):
                converted += '%sMILLONES ' % self.convert_group(millones)

        if (miles):
            if (miles == '001'):
                converted += 'MIL '
            elif (int(miles) > 0):
                converted += '%sMIL ' % self.convert_group(miles)

        if (cientos):
            if (cientos == '001'):
                converted += 'UN '
            elif (int(cientos) > 0):
                converted += '%s ' % self.convert_group(cientos)
        if (centavos) > 0:
            converted += "con %2i/100 " % centavos
        converted += moneda
        return converted.title()

    def convert_group(self, n):
        UNIDADES = (
            '',
            'UN ',
            'DOS ',
            'TRES ',
            'CUATRO ',
            'CINCO ',
            'SEIS ',
            'SIETE ',
            'OCHO ',
            'NUEVE ',
            'DIEZ ',
            'ONCE ',
            'DOCE ',
            'TRECE ',
            'CATORCE ',
            'QUINCE ',
            'DIECISEIS ',
            'DIECISIETE ',
            'DIECIOCHO ',
            'DIECINUEVE ',
            'VEINTE '
        )
        DECENAS = (
            'VEINTI',
            'TREINTA ',
            'CUARENTA ',
            'CINCUENTA ',
            'SESENTA ',
            'SETENTA ',
            'OCHENTA ',
            'NOVENTA ',
            'CIEN '
        )

        CENTENAS = (
            'CIENTO ',
            'DOSCIENTOS ',
            'TRESCIENTOS ',
            'CUATROCIENTOS ',
            'QUINIENTOS ',
            'SEISCIENTOS ',
            'SETECIENTOS ',
            'OCHOCIENTOS ',
            'NOVECIENTOS '
        )
        MONEDAS = (
            {'country': u'Colombia', 'currency': 'COP', 'singular': u'PESO COLOMBIANO', 'plural': u'PESOS COLOMBIANOS',
             'symbol': u'$'},
            {'country': u'Honduras', 'currency': 'HNL', 'singular': u'Lempira', 'plural': u'Lempiras', 'symbol': u'L'},
            {'country': u'Estados Unidos', 'currency': 'USD', 'singular': u'DÓLAR', 'plural': u'DÓLARES',
             'symbol': u'US$'},
            {'country': u'Europa', 'currency': 'EUR', 'singular': u'EURO', 'plural': u'EUROS', 'symbol': u'€'},
            {'country': u'México', 'currency': 'MXN', 'singular': u'PESO MEXICANO', 'plural': u'PESOS MEXICANOS',
             'symbol': u'$'},
            {'country': u'Perú', 'currency': 'PEN', 'singular': u'NUEVO SOL', 'plural': u'NUEVOS SOLES',
             'symbol': u'S/.'},
            {'country': u'Reino Unido', 'currency': 'GBP', 'singular': u'LIBRA', 'plural': u'LIBRAS', 'symbol': u'£'}
        )
        output = ''

        if (n == '100'):
            output = "CIEN "
        elif (n[0] != '0'):
            output = CENTENAS[int(n[0]) - 1]

        k = int(n[1:])
        if (k <= 20):
            output += UNIDADES[k]
        else:
            if ((k > 30) & (n[2] != '0')):
                output += '%sY %s' % (DECENAS[int(n[1]) - 2], UNIDADES[int(n[2])])
            else:
                output += '%s%s' % (DECENAS[int(n[1]) - 2], UNIDADES[int(n[2])])

        return output

class PaymentInvoiceLine(models.Model):
    _inherit = 'payment.invoice.line'

    amount_retention_1 = fields.Float(string='Ret 1%')
    amount_retention_12_5 = fields.Float(string='Ret 12.5%')
    amount_retention_15 = fields.Float(string='Ret 15%')
