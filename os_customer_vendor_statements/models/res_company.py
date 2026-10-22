from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

Days = [('D_0', 'Monday'), ('D_1', 'Tuesday'), ('D_2', 'Wednesday'), ('D_3', 'Thursday'), ('D_4', 'Friday'),
        ('D_5', 'Saturday'), ('D_6', 'Sunday')]


class ResCompanyData(models.Model):
    _inherit = 'res.company'

    overdue_sent_date = fields.Integer("Overdue Statement Send Date")
    enable_overdue_sent = fields.Boolean("Send Overdue customer Statement")
    enable_customer_statements = fields.Boolean("Send customer's Statement")
    overdue_temp_id = fields.Many2one('mail.template', 'Template for Overdue Statements',
                                      domain=[('model', '=', 'res.partner')])
    monthly_statement_auto_upt = fields.Boolean("Auto Monthly Statement")
    weekly_statement_auto_upt = fields.Boolean("Auto Weekly Statement")
    sent_day_weekly = fields.Selection(Days, string="Weekly Send Day")
    monthly_sent_day = fields.Integer("Monthly Send Day")
    mail_template_weekly_id = fields.Many2one('mail.template', 'Weekly Statement Email Template',
                                              domain=[('model', '=', 'res.partner')])
    mail_template_monthly_id = fields.Many2one('mail.template', 'Monthly Statement Email Template',
                                              domain=[('model', '=', 'res.partner')])

    def _datetime_selection(self, days):
        now = datetime.now()
        expected_date = datetime(now.year, now.month, days, now.hour, now.minute, now.second)
        date_scheduled = expected_date + relativedelta(months=+1) if now.day > days else expected_date
        return date_scheduled

    @api.onchange('enable_overdue_sent')
    def _onchange_enable_overdue_sent(self):
        if self.enable_overdue_sent:
            ir_overdue_ref = self.env.ref('os_customer_vendor_statements.ir_cron_customer_overdue_statements')
            ir_overdue_ref.active = self.enable_overdue_sent
            date_scheduled = self._datetime_selection(self.overdue_sent_date)
            ir_overdue_ref.nextcall = str(date_scheduled)

    @api.onchange('enable_customer_statements', 'monthly_statement_auto_upt')
    def _onchange_enable_customer_statements(self):
        if self.enable_customer_statements and self.monthly_statement_auto_upt:
            ir_monthly_ref = self.env.ref('os_customer_vendor_statements.ir_cron_monthly_customer_statements')
            ir_monthly_ref.active = self.monthly_statement_auto_upt
            date_scheduled = self._datetime_selection(self.monthly_sent_day)
            ir_monthly_ref.nextcall = str(date_scheduled)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.constrains('overdue_sent_date', 'monthly_statement_flag')
    def _check_valid_dates(self):
        if self.enable_overdue_sent and self.overdue_sent_date > 31 or self.overdue_sent_date <= 0:
            raise ValidationError(_('Date range is not valid for taking Overdue Statements!'))
        if self.monthly_sent_day and self.monthly_sent_day > 31 or self.monthly_sent_day <= 0:
            raise ValidationError(_('Date range is not valid for taking Statements'))

    overdue_sent_date = fields.Integer("Overdue Statement Send Date", related='company_id.overdue_sent_date',
                                       readonly=False)
    enable_overdue_sent = fields.Boolean("Send Overdue Customer Statement",
                                         related='company_id.enable_overdue_sent',
                                         readonly=False)
    overdue_temp_id = fields.Many2one('mail.template', 'Template for Overdue Statements',
                                      domain=[('model', '=', 'res.partner')],
                                      related='company_id.overdue_temp_id',
                                      readonly=False)
    enable_customer_statements = fields.Boolean("Send Customer's Statement",
                                                related='company_id.enable_customer_statements',
                                                readonly=False)
    monthly_statement_auto_upt = fields.Boolean("Auto Monthly Statement",
                                                related='company_id.monthly_statement_auto_upt',
                                                readonly=False)
    weekly_statement_auto_upt = fields.Boolean("Auto Weekly Statement", related='company_id.weekly_statement_auto_upt',
                                               readonly=False)
    sent_day_weekly = fields.Selection(string="Weekly Send Day",
                                       related='company_id.sent_day_weekly',
                                       readonly=False)
    monthly_sent_day = fields.Integer("Monthly Send Day", related='company_id.monthly_sent_day',
                                      readonly=False)
    mail_template_weekly_id = fields.Many2one('mail.template', 'Weekly Statement Email Template',
                                              domain=[('model', '=', 'res.partner')],
                                              related='company_id.mail_template_weekly_id',
                                              readonly=False)
    mail_template_monthly_id = fields.Many2one('mail.template', 'Monthly Statement Email Template',
                                               domain=[('model', '=', 'res.partner')],
                                               related='company_id.mail_template_monthly_id',
                                               readonly=False)
