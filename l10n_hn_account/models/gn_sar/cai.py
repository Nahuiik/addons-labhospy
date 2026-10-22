from odoo import models, fields, api, _
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class fiscal_regime(models.Model):
    _name = "dei.fiscal_regime"
    _description = "Fiscal Regime"

    cai = fields.Many2one('dei.cai', required=True)
    sequence = fields.Many2one('ir.sequence')
    selected = fields.Boolean('selected')
    desde = fields.Integer('From')
    hasta = fields.Integer('to')

class cai(models.Model):
    _name = "dei.cai"
    _description = "Clave de Autorización de Impresión"
    _inherit = ['mail.thread', 'mail.activity.mixin']


    name = fields.Char('CAI', help='Clave de Autorización de Impresión ', required=True, index=True)
    expiration_date = fields.Date('Expiration Date', required=True, index=True)
    # active = fields.Boolean('active')
    company = fields.Many2one('res.company', required=True)
    fiscal_regimes = fields.One2many('dei.fiscal_regime', 'cai')
    notify_user_ids = fields.Many2many('res.users', string="Notification Users")
    notify_before = fields.Integer(string="Notify Before", default=3)
    sequence_exceed_limit = fields.Integer(string="Sequence Limit Email")

    @api.model
    def send_cai_expiry_mail(self):
        """Sending cai expiry notification."""
        cai_ids = self.env['dei.cai'].search([])
        for rec in cai_ids:

            notify_days = rec.notify_before
            if not notify_days or not rec.notify_user_ids:
                continue
            user_ids = rec.notify_user_ids
            email_lst = list(set(user_ids.filtered(
                lambda i: i.email).mapped('email')))
            email_to = ','.join([str(i) for i in email_lst])
            email_values = {'email_to': email_to}
            template_id = self.env.ref(
                'l10n_hn_account.cai_expiry_notify_mail_template')


            now = datetime.now()
            date_now = now.date()
            exp_date = fields.Date.from_string(
                rec.expiration_date) - timedelta(days=notify_days)
            if exp_date == date_now:
                mail_id = template_id.send_mail(rec.id,
                                      force_send=True,
                                      email_values=email_values)

