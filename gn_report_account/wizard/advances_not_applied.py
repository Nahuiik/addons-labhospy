from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class AdvancesNotAppliedWizard(models.TransientModel):
    _name = 'advances.not.applied.wizard'
    _description = 'Wizard report advances not applied'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    
    
    @api.model
    def get_actual_year(self):
        return datetime.now().year

    def action_print_report(self):
        vals = {
            'start_date': self.start_date,
            'end_date': self.end_date, 
        }
        data = vals
        data['model'] = 'advances.not.applied.wizard'
        data['form'] = self.read()[0]
        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        return self.env.ref('gn_report_account.action_advance_not_applied_xls').report_action(self, data=data)

    @api.constrains('start_date','end_date')
    def validate_dates(self):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError(_('The initial date can not be greater than the final.'))
