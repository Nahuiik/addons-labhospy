from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)


class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'

    def validate_and_send_invoice(self, invoice):
        self.ensure_one()
        invoice.action_post()
        email_context = self.env.context.copy()
        email_context.update({
            'total_amount': invoice.amount_total,
            'email_to': self.partner_id.email,
            'code': self.code,
            'currency': self.pricelist_id.currency_id.name,
            'date_end': self.date,
        })
        _logger.debug("Sending Invoice Mail to %s for subscription %s", self.partner_id.email, self.id)
        self.template_id.invoice_mail_template_id.with_context(email_context).send_mail(invoice.id)
        invoice.is_move_sent = True