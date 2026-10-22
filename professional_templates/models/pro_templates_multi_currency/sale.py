from num2words import num2words
from odoo import models, fields, api
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from datetime import date, timedelta
import logging
import psycopg2
_logger = logging.getLogger(__name__)


class SO(models.Model):
    _inherit = "sale.order"

    exch_rate = fields.Float('Exchange Rate', related="currency_rate", digits=(16, 4))
    amount_local = fields.Float(
        'Amount in Local Currency',
        compute='_compute_amount_local')
    company_currency_id = fields.Many2one(
        'res.currency',
        'Company Currency',
        related='company_id.currency_id')

    # currency_rate = fields.Float('Rate',digits=(12, 6))
    is_same_currency = fields.Boolean('Same Currency')
    amount_total_text = fields.Char("Amount in Word", compute='_compute_amount_local', default='Cero')
    currency_rate = fields.Float("Currency Rate", compute='_compute_currency_rate', compute_sudo=True, store=True,
                                 digits=(12, 6), readonly=False,
                                 help='The rate of the currency to the currency of rate 1 applicable at the date of the order')
    amount_in_words = fields.Char(compute='_compute_amount_local', string="Amount in Words")
    print_to_local = fields.Boolean(string="Show in Local", default=True)

    @api.depends('exch_rate', 'amount_total')
    def _compute_amount_local(self):
        for order in self:
            order.amount_local = order.exch_rate * order.amount_total
            if order.is_same_currency:
                order.amount_in_words = order.company_id.currency_id.amount_to_text(order.amount_total)
            else:
                if order.print_to_local:
                    order.amount_in_words = order.company_id.currency_id.amount_to_text(order.amount_local)
                else:
                    order.amount_in_words = order.currency_id.amount_to_text(order.amount_local)
            order.amount_total_text = order.amount_in_words

    @api.depends('pricelist_id', 'date_order', 'company_id')
    def _compute_currency_rate(self):
        for order in self:
            if order.currency_id and order.date_order:
                order.is_same_currency = order.currency_id.id == order.company_id.currency_id.id
                order.currency_rate = order.currency_id._get_conversion_rate(order.currency_id, order.company_id.currency_id, order.company_id, order.date_order.date())
            else:
                order.currency_rate = 0.0

    def _prepare_invoice(self):
        """
        overwrite to pass extra fields
        """
        res = super(SO, self)._prepare_invoice()
        res.update({'currency_rate':self.currency_rate,
                    'is_same_currency':self.is_same_currency,
                    })
        return res
