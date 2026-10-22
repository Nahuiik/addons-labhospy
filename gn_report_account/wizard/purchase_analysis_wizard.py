from odoo import fields, models, api
from odoo.exceptions import UserError


class PurcharseAnalysis(models.TransientModel):
    _name = 'purcharse.analysis.report'
    _description = 'Purcharse Analysis'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    
    def action_print_report(self):
        vals = {
            'start_date': self.start_date,
            'end_date': self.end_date,
        }
        data = vals
        data['model'] = 'purcharse.analysis.report'
        data['form'] = self.read()[0]
        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        return self.env.ref('gn_report_account.action_purcharse_analysis_xls').report_action(self, data=data)

