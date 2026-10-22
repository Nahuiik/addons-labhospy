# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, date_utils
# Si más adelante validas correos, en Odoo 19 usa:
# from odoo.tools import email_normalize, email_split
from odoo.tools.misc import formatLang, format_date, get_lang
from collections import defaultdict


class PaymentWthLine(models.Model):
    _name = 'payment.wht.line'

    payment_id = fields.Many2one('account.payment', string="Account Payment")
    account_id = fields.Many2one('account.account', string="Account")
    name = fields.Char(string="Label")
    amount_wht = fields.Float(string="Amount")


class BuktiPotongPayment(models.Model):
    _name = 'bukti.potong.payment'

    date_terima_bukti_potong = fields.Date(string="Tanggal Terima Bukti Potong")
    partner_id = fields.Many2one('res.partner', string="Customer / Vendor")
    number_bukti_potong = fields.Char(string="No. Bukti Potong")
    jumlah = fields.Float(string="Jumlah")
    date_bukti_potong = fields.Date(string="Tanggal Bukti Potong")
    sisa = fields.Float(string="Sisa")
    payment_id = fields.Many2one('account.payment', string="Payment")
    state = fields.Selection(
        [("draft", "Draft"), ("confirm", "Confirmed"), ("validate", "Validated")],
        string="status", default='draft', required=False,
    )
    pph_id = fields.Many2one('account.tax', string="PPH")

    @api.onchange('partner_id')
    def onchange_payment_id(self):
        payment_ids = self.env['account.payment'].search([('partner_id', '=', self.partner_id.id)])
        return {'domain': {'payment_id': [('id', 'in', payment_ids.ids)]}}

    def name_get(self):
        res = []
        for order in self:
            name = order.number_bukti_potong or _('Bukti Potong')
            res.append((order.id, name))
        return res

    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_validate(self):
        self.write({'state': 'validate'})

    def action_draft(self):
        self.write({'state': 'draft'})


class AccountPayment(models.Model):
    _inherit = "account.payment"

    wht_line_ids = fields.One2many("payment.wht.line", 'payment_id', string="Payment Register Line")
    is_wht_trx = fields.Boolean(string="Multiple Writeoff")
    is_pass_writeoff = fields.Boolean(string="is Pass Writeoff", help="pass write-off journal items with multi account")
    bukti_potong_ids = fields.One2many("bukti.potong.payment", 'payment_id', string="Bukti potong Line")

    @api.onchange('is_internal_transfer')
    def _onchange_product(self):
        if self.is_internal_transfer:
            self.is_wht_trx = False

    def _synchronize_from_moves(self, changed_fields):
        """
        En Odoo 19, evita 'return' dentro del loop para no cortar la sincronización.
        Llama primero al super() para el comportamiento estándar y luego aplica
        los ajustes sólo cuando is_wht_trx está activo.
        """
        res = super(AccountPayment, self)._synchronize_from_moves(changed_fields)

        if self._context.get('skip_account_move_synchronization'):
            return res

        for pay in self.with_context(skip_account_move_synchronization=True):
            if not pay.is_wht_trx:
                continue

            # Si el asiento está vinculado a statement line, no sincronizamos desde payment.
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

                if len(liquidity_lines) != 1 or len(counterpart_lines) != 1:
                    raise UserError(_(
                        "The journal entry %s reached an invalid state relative to its payment.\n"
                        "To be consistent, the journal entry must always contains:\n"
                        "- one journal item involving the outstanding payment/receipts account.\n"
                        "- one journal item involving a receivable/payable account.\n"
                        "- optional journal items, all sharing the same account.\n\n"
                    ) % move.display_name)

                if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
                    raise UserError(_(
                        "The journal entry %s reached an invalid state relative to its payment.\n"
                        "To be consistent, the journal items must share the same currency."
                    ) % move.display_name)

                if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
                    raise UserError(_(
                        "The journal entry %s reached an invalid state relative to its payment.\n"
                        "To be consistent, the journal items must share the same partner."
                    ) % move.display_name)

                partner_type = 'customer' if counterpart_lines.account_id.user_type_id.type == 'receivable' else 'supplier'
                liquidity_amount = liquidity_lines.amount_currency

                move_vals_to_write.update({
                    'currency_id': liquidity_lines.currency_id.id,
                    'partner_id': liquidity_lines.partner_id.id,
                })
                payment_vals_to_write.update({
                    'amount': abs(liquidity_amount),
                    'partner_type': partner_type,
                    'currency_id': liquidity_lines.currency_id.id,
                    'destination_account_id': counterpart_lines.account_id.id,
                    'partner_id': liquidity_lines.partner_id.id,
                })
                if liquidity_amount > 0.0:
                    payment_vals_to_write.update({'payment_type': 'inbound'})
                elif liquidity_amount < 0.0:
                    payment_vals_to_write.update({'payment_type': 'outbound'})

            move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
            pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))

        return res


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        print("_post AP OVERRIDE RUNNING..........................")
        res = super(AccountMove, self)._post(soft=soft)
        # 'res' puede ser un recordset; iteramos por seguridad.
        for move_id in res:
            payment_id = self.env['account.payment'].search([('move_id', '=', move_id.id)], limit=1)
            temp = []
            if payment_id and payment_id.wht_line_ids and payment_id.line_ids:
                if not payment_id.is_pass_writeoff:
                    move_id.button_draft_wht()
                    if payment_id.line_ids and payment_id.partner_type == 'customer':
                        for data in payment_id.line_ids:
                            if payment_id.destination_account_id == data.account_id:
                                wht_amount = sum(rec.amount_wht for rec in payment_id.wht_line_ids.filtered(lambda m: m.amount_wht > 0))
                                credit = payment_id.amount + wht_amount
                                vals = {'credit': credit}
                                temp.append((1, data.id, vals))
                            elif payment_id.journal_id.payment_debit_account_id == data.account_id:
                                wht_amount_debit = sum(rec.amount_wht for rec in payment_id.wht_line_ids.filtered(lambda m: m.amount_wht < 0))
                                debit = payment_id.amount + (-wht_amount_debit)
                                vals = {'debit': debit}
                                temp.append((1, data.id, vals))
                            if data.is_wht:
                                temp.append((2, data.id))
                        for line in payment_id.wht_line_ids:
                            if line.amount_wht > 0:
                                wht_vals = {
                                    'name': line.name,
                                    'debit': line.amount_wht,
                                    'credit': 0.0,
                                    'partner_id': payment_id.partner_id.id,
                                    'account_id': line.account_id.id,
                                    'is_wht': True
                                }
                                temp.append((0, 0, wht_vals))
                            else:
                                wht_vals = {
                                    'name': line.name,
                                    'debit': 0.0,
                                    'credit': -line.amount_wht,
                                    'partner_id': payment_id.partner_id.id,
                                    'account_id': line.account_id.id,
                                    'is_wht': True
                                }
                                temp.append((0, 0, wht_vals))
                    else:
                        if payment_id.line_ids and payment_id.partner_type == 'supplier':
                            for data in payment_id.line_ids:
                                if payment_id.destination_account_id == data.account_id:
                                    wht_amount = sum(rec.amount_wht for rec in payment_id.wht_line_ids.filtered(lambda m: m.amount_wht > 0))
                                    debit = payment_id.amount + wht_amount
                                    vals = {'debit': debit}
                                    temp.append((1, data.id, vals))
                                elif payment_id.journal_id.payment_debit_account_id == data.account_id:
                                    wht_amount_debit = sum(rec.amount_wht for rec in payment_id.wht_line_ids.filtered(lambda m: m.amount_wht < 0))
                                    credit = payment_id.amount + (-wht_amount_debit)
                                    vals = {'credit': credit}
                                    temp.append((1, data.id, vals))
                                if data.is_wht:
                                    temp.append((2, data.id))
                            for line in payment_id.wht_line_ids:
                                if line.amount_wht > 0:
                                    wht_vals = {
                                        'name': line.name,
                                        'debit': 0.0,
                                        'credit': line.amount_wht,
                                        'partner_id': payment_id.partner_id.id,
                                        'account_id': line.account_id.id,
                                        'is_wht': True
                                    }
                                    temp.append((0, 0, wht_vals))
                                else:
                                    wht_vals = {
                                        'name': line.name,
                                        'debit': -line.amount_wht,
                                        'credit': 0.0,
                                        'partner_id': payment_id.partner_id.id,
                                        'account_id': line.account_id.id,
                                        'is_wht': True
                                    }
                                    temp.append((0, 0, wht_vals))

                    if temp:
                        payment_id.with_context(check_move_validity=False).write({'line_ids': temp})

                    if not payment_id.is_pass_writeoff:
                        payment_id.write({'is_pass_writeoff': True})
                        move_id._check_balanced()
                        move_id.with_context(check_move_validity=True).action_post()
        return res

    def button_draft(self):
        res = super(AccountMove, self).button_draft()
        payment_id = self.env['account.payment'].search([('move_id', '=', self.id)])
        if payment_id:
            payment_id.write({'is_pass_writeoff': False})
        return res

    def button_draft_wht(self):
        print("button_draft_wht RUNNING........................")
        AccountMoveLine = self.env['account.move.line']
        excluded_move_ids = []

        if self._context.get('suspense_moves_mode'):
            excluded_move_ids = AccountMoveLine.search(
                AccountMoveLine._get_suspense_moves_domain() + [('move_id', 'in', self.ids)]
            ).mapped('move_id').ids

        for move in self:
            if move in move.line_ids.mapped('full_reconcile_id.exchange_move_id'):
                raise UserError(_('You cannot reset to draft an exchange difference journal entry.'))
            if move.tax_cash_basis_rec_id:
                raise UserError(_('You cannot reset to draft a tax cash basis journal entry.'))
            if move.restrict_mode_hash_table and move.state == 'posted' and move.id not in excluded_move_ids:
                raise UserError(_('You cannot modify a posted entry of this journal because it is in strict mode.'))
            # Eliminamos analíticas
            move.mapped('line_ids.analytic_line_ids').unlink()

        self.mapped('line_ids').remove_move_reconcile()
        self.write({'state': 'draft', 'is_move_sent': False})


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    is_wht = fields.Boolean(string="is WHT")