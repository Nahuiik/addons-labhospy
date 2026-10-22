from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang, format_date, get_lang



class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _get_default_line_name(self, document, amount, currency, date, partner=None):
        ''' Helper to construct a default label to set on journal items.

        E.g. Vendor Reimbursement $ 1,555.00 - Azure Interior - 05/14/2020.

        :param document:    A string representing the type of the document.
        :param amount:      The document's amount.
        :param currency:    The document's currency.
        :param date:        The document's date.
        :param partner:     The optional partner.
        :return:            A string.
        '''
        values = ['%s %s' % (document, formatLang(self.env, amount, currency_obj=currency))]
        if partner:
            values.append(partner.display_name)
        values.append(format_date(self.env, fields.Date.to_string(date)))
        return ' - '.join(values)
    


class account_register_payment(models.TransientModel):
    _inherit = "account.payment.register"

    post_diff_in = fields.Selection([
        ('single', 'Single Account'),
        ('multi', 'Multiple Account')],
        string="Post Difference In", default='single', copy=False)
    write_off_lines = fields.One2many('account.payment.writeoff', 'payment_id', string="Writeoff Lines", copy=False)

    @api.model
    def _gts_payment_invoice_label(self, move):
        """Etiqueta del memo: número de factura, no cotización/OC en ref."""
        if move.move_type in ('out_invoice', 'out_refund'):
            return move.name or move.payment_reference or move.ref
        supplier_num = getattr(move, 'supplier_invoice_number', None)
        return supplier_num or move.ref or move.name or move.payment_reference

    @api.model
    def _get_communication(self, lines):
        moves = lines.move_id
        invoice_moves = moves.filtered(lambda m: m.is_invoice(include_receipts=True))
        if invoice_moves and len(invoice_moves) == len(moves):
            labels = sorted(filter(None, {self._gts_payment_invoice_label(m) for m in invoice_moves}))
            if len(labels) == 1:
                return labels[0]
            if labels:
                return ', '.join(labels)
        return super()._get_communication(lines)


    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)

        payment_vals.update({
            'payment_reference': self.communication,
            'destination_account_id': self.line_ids[0].account_id.id,
        })

        if self.payment_move_type_dep:
            payment_vals['payment_move_type_dep'] = self.payment_move_type_dep
        else:
            payment_vals['payment_move_type'] = self.payment_move_type

        invoice_amounts = {}
        invoice_totals = {}
        invoice_residuals = {}
        lines = batch_result.get('lines') if isinstance(batch_result, dict) else batch_result
        for aml in lines or self.env['account.move.line']:
            move = aml.move_id
            if not move:
                continue
            amount_currency = aml.amount_residual_currency if aml.currency_id else aml.amount_residual
            amount_to_pay = abs(amount_currency)
            invoice_amounts[move.id] = invoice_amounts.get(move.id, 0.0) + amount_to_pay
            invoice_totals.setdefault(move.id, abs(move.amount_total))
            invoice_residuals.setdefault(move.id, abs(move.amount_residual))

        # Pagos parciales: el asistente trae self.amount (importe real del pago). Antes se
        # rellenaba cada línea con el residual completo, sumando más que el pago y disparando
        # _check_invoice_amount ("No puede seleccionar facturas por un monto mayor al pago").
        if invoice_amounts:
            wizard_amount = abs(self.amount)
            total_alloc = sum(invoice_amounts.values())
            currency = self.currency_id
            if currency.compare_amounts(total_alloc, wizard_amount) == 1:
                move_ids = list(invoice_amounts.keys())
                allocated = 0.0
                for i, move_id in enumerate(move_ids):
                    if i == len(move_ids) - 1:
                        invoice_amounts[move_id] = currency.round(wizard_amount - allocated)
                    else:
                        share = (
                            invoice_amounts[move_id] / total_alloc
                            if total_alloc
                            else 0.0
                        )
                        part = currency.round(wizard_amount * share)
                        invoice_amounts[move_id] = part
                        allocated += part

            payment_vals['invoice_lines'] = [
                (0, 0, {
                    'invoice_id': move_id,
                    'amount': amount,
                    'amount_total': invoice_totals.get(move_id, amount),
                    'residual': invoice_residuals.get(move_id, amount),
                })
                for move_id, amount in invoice_amounts.items()
            ]

        # No duplicar líneas: el bucle anterior ya incluye active_id vía batch_result['lines'].

        if not self.currency_id.is_zero(self.payment_difference) and self.payment_difference_handling == 'reconcile':
            if self.post_diff_in == 'multi':
                write_off_line_vals = list(payment_vals.get('write_off_line_vals', []))
                payment_vals['post_diff_in'] = 'multi'
                payment_vals.setdefault('write_off_lines', [])

                for line in self.write_off_lines:
                    amount_currency = line.amount
                    if self.payment_type == 'outbound':
                        amount_currency *= -1
                    balance = self.currency_id._convert(
                        amount_currency,
                        self.company_id.currency_id,
                        self.company_id,
                        self.payment_date,
                    )
                    write_off_line_vals.append({
                        'name': line.description or line.account_id.display_name,
                        'account_id': line.account_id.id,
                        'partner_id': self.partner_id.id,
                        'currency_id': self.currency_id.id,
                        'amount_currency': amount_currency,
                        'balance': balance,
                    })
                    payment_vals['write_off_lines'].append((0, 0, {
                        'account_id': line.account_id.id,
                        'description': line.description,
                        'amount_per': line.amount_per,
                        'amount': line.amount,
                    }))

                payment_vals['write_off_line_vals'] = write_off_line_vals

        return payment_vals
    
    @api.depends(
        'can_edit_wizard',
        'amount',
        'batches',
        'installments_mode',
        'custom_user_amount',
        'line_ids',
    )
    def _compute_communication(self):
        super()._compute_communication()
        for wizard in self:
            if wizard.communication:
                if not wizard.communication.upper().startswith('PAGO DE FACTURA'):
                    wizard.communication = f"PAGO DE FACTURA {wizard.communication}"
            else:
                wizard.communication = False
                
                




class account_payment(models.Model):
    _inherit = "account.payment"

    post_diff_in = fields.Selection([
        ('single', 'Single Account'),
        ('multi', 'Multiple Account')],
        string="Post Difference In", default='single', copy=False)
    write_off_lines = fields.One2many('account.payment.writeoff', 'payment_id', string="Writeoff Lines", copy=False)

    # new field for writeoff
    # payment_difference = fields.Monetary(
    #     compute='_compute_payment_difference')
    payment_difference_handling = fields.Selection([
        ('open', 'Keep open'),
        ('reconcile', 'Mark as fully paid'),
    ], default='open', string="Payment Difference Handling")
    writeoff_account_id = fields.Many2one('account.account', string="Difference Account", copy=False,
                                          domain="[('deprecated', '=', False), ('company_id', '=', company_id)]")
    writeoff_label = fields.Char(string='Journal Item Label', default='Write-Off',
                                 help='Change label of the counterpart that will hold the payment difference')

    def _synchronize_from_moves(self, changed_fields):
        if self._context.get('skip_account_move_synchronization'):
            return
        for pay in self.with_context(skip_account_move_synchronization=True):
            if pay.post_diff_in == 'multi':
                if pay.move_id.statement_line_id:
                    continue
                move = pay.move_id
                move_vals_to_write = {}
                payment_vals_to_write = {}

                if 'journal_id' in changed_fields:
                    if pay.journal_id.type not in ('bank', 'cash'):
                        raise UserError(_("A payment must always belongs to a bank or cash journal."))

                if 'line_ids' in changed_fields:
                    all_lines = move.line_ids
                    liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

                    if counterpart_lines.account_id.account_type == 'asset_receivable':
                        partner_type = 'customer'
                    else:
                        partner_type = 'supplier'
                    for liquid in liquidity_lines:
                        liquidity_amount = liquid.amount_currency
                        move_vals_to_write.update({
                            'currency_id': liquid.currency_id.id,
                            'partner_id': liquid.partner_id.id,
                        })
                        payment_vals_to_write.update({
                            'amount': abs(liquidity_amount),
                            'payment_type': 'inbound' if liquidity_amount > 0.0 else 'outbound',
                            'partner_type': partner_type,
                            'currency_id': liquid.currency_id.id,
                            # 'destination_account_id': counterpart_lines.account_id.id,
                            'partner_id': liquid.partner_id.id,
                        })

                move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
                pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))
        # else:
        #     return super(account_payment, self)._synchronize_from_moves(changed_fields=changed_fields)

    def _seek_for_lines(self):
        ''' Helper used to dispatch the journal items between:
        - The lines using the temporary liquidity account.
        - The lines using the counterpart account.
        - The lines being the write-off lines.
        :return: (liquidity_lines, counterpart_lines, writeoff_lines)
        '''
        self.ensure_one()

        liquidity_lines = self.env['account.move.line']
        counterpart_lines = self.env['account.move.line']
        writeoff_lines = self.env['account.move.line']

        valid_account_types = self._get_valid_payment_account_types()
        for line in self.move_id.line_ids:
            if line.account_id in self._get_valid_liquidity_accounts():
                liquidity_lines += line
            elif line.account_id.account_type in valid_account_types or line.account_id == self.company_id.transfer_account_id:
                if not line.is_writeoff_line:
                    counterpart_lines += line
            else:
                writeoff_lines += line

        return liquidity_lines, counterpart_lines, writeoff_lines



class payment_writeoff(models.Model):
    _name = "payment.writeoff"
    _description = "payment.writeoff"

    payment_id = fields.Many2one('account.payment', string="Payment")
    account_id = fields.Many2one('account.account', string="Difference Account")
    description = fields.Char(string="Description")
    amount_per = fields.Float(string="Payment Amount(%)")
    amount = fields.Float(string="Payment Amount")


class account_payment_writeoff(models.TransientModel):
    _name = "account.payment.writeoff"
    _description = "account.payment.writeoff"

    payment_id_form = fields.Many2one('account.payment', string="Payment Record")
    payment_id = fields.Many2one('account.payment.register', string="Payment")
    account_id = fields.Many2one('account.account', string="Difference Account")
    description = fields.Char(string="Description")
    amount_per = fields.Float(string="Payment Amount(%)")
    amount = fields.Float(string="Payment Amount")

    @api.onchange('amount_per')
    def _get_amount_by_percentage(self):
        try:
            self.amount = (self.payment_id.payment_difference * self.amount_per) / 100
        except:
            self.amount = 0

    @api.onchange('amount')
    def _get_percentage_by_amount(self):
        try:
            self.amount_per = (self.amount * 100) / self.payment_id.payment_difference
        except:
            self.amount_per = 0
