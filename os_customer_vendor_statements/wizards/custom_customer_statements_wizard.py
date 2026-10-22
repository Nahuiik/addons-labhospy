from dateutil.relativedelta import relativedelta
from odoo import fields, models, api


class CustomStatementWizard(models.TransientModel):
    _name = 'custom.customer.statement.wizard'
    _description = 'Send Custom Customer Statements'

    custom_period = fields.Selection([
        ('30', 'Thirty Days'),
        ('60', 'Sixty Days'),
        ('90', 'Ninety Days'),
        ('3_month', 'Quarter'),
        ('custom', 'Custom Date Range'),
    ], string="Duration", required=True, default="30")
    c_date_to = fields.Date(string='To Date')
    c_date_from = fields.Date(string='From Date')

    def action_custom_customer_statement(self):
        ResPartner = self.env['res.partner']
        for partner in ResPartner.browse(self._context.get('active_ids', [])):
            partner.custom_period = self.custom_period
            if self.custom_period:
                if self.custom_period == '30' or '60' or '90':
                    partner.c_date_from = fields.Date.today() - relativedelta(days=int(self.custom_period))
                    partner.c_date_to = fields.Date.today()
                elif self.custom_period == 'custom':
                    partner.c_date_from = fields.Date.today() - relativedelta(months=3)
                    partner.c_date_to = fields.Date.today()
                else:
                    partner.c_date_from = False
                    partner.c_date_to = False
            partner._sent_email_custom_customer_statements()
