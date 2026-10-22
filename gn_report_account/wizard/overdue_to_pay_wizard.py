from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
class OverdueToPay(models.TransientModel):
    _name = 'overdue.to.pay'
    _description = 'Wizard overdue to pay report'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    def action_generate_report(self):
        for rec in self:
            vals = {
                'start_date': self.start_date,
                'end_date': self.end_date,
            }
            data = vals
            data['model'] = 'overdue.to.pay'
            data['form'] = self.read()[0]
            for field in data['form'].keys():
                if isinstance(data['form'][field], tuple):
                    data['form'][field] = data['form'][field][0]
            return self.env.ref('gn_report_account.action_report_overdue_to_pay_xlsx').report_action(self, data=data)
    
    @api.constrains('start_date','end_date')
    def validate_dates(self):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError(_('The initial date can not be greater than the final.'))