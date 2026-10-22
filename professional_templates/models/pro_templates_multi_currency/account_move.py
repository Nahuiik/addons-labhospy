from num2words import num2words
from odoo import models, fields, api
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from datetime import date, timedelta
import logging
import psycopg2
_logger = logging.getLogger(__name__)


class Invoice(models.Model):
    _inherit = "account.move"

    exch_rate = fields.Float('Exchange Rate', related="currency_rate", digits=(16, 4))
    amount_local = fields.Float('Amount in Local Currency',compute='_compute_amount_local')
    company_currency_id = fields.Many2one('res.currency','Company Currency',related='company_id.currency_id')
    due_amount_local = fields.Float('Due Amount in Local Currency',compute='_compute_amount_local')

    currency_rate = fields.Float(
        'Multi-currency exchange rate',
        digits=(12, 6),
        readonly=False,
    )
    is_same_currency = fields.Boolean(compute='_check_same_currency', string='Same Currency')
    amount_in_words = fields.Char(compute='_compute_amount_local', string="Amount in Words")
    print_to_local = fields.Boolean(string="Show in Local", default=True)

    @api.depends('currency_id')
    def _check_same_currency(self):
        for inv in self:
            inv.is_same_currency = bool(inv.currency_id and inv.company_id.currency_id and inv.currency_id == inv.company_id.currency_id)


    @api.onchange('currency_id','invoice_date')
    def onchage_currency_id(self):
        for inv in self:
            if inv.currency_id and inv.invoice_date:
                inv.is_same_currency = inv.currency_id.id == inv.company_id.currency_id.id
                inv.currency_rate = inv.currency_id._get_conversion_rate(inv.currency_id, inv.company_id.currency_id, inv.company_id, inv.invoice_date)
            else:
                inv.currency_rate = 0.0

    @api.depends('exch_rate', 'amount_total', 'amount_total_signed', 'amount_residual_signed')
    def _compute_amount_local(self):
        for move in self:
            move.amount_local = move.amount_total_signed
            move.due_amount_local = move.amount_residual_signed
            # amount_total_signed es negativo en compras (pasivo); en letras debe coincidir con el total mostrado
            move.amount_in_words = move.company_id.currency_id.amount_to_text(
                abs(move.amount_total_signed)
            )


#   select id,move_name,company_currency_id,currency_id,reconcile_model_id,payment_id,tax_line_id,full_reconcile_id,debit,credit,balance,amount_currency,amount_residual,amount_residual_currency,reconciled from account_move_line where move_id=10312;
