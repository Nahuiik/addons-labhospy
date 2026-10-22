from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RetentionReportWizard(models.TransientModel):
    _name = 'retention.report.wizard'


    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    report_type = fields.Selection([('1_per', '1% Retention'),
                                    ('12_per', '12.5% Retention'),
                                    ('15_per', '15% Retención')
                                    ],
                                   string="Report Type")

    def action_get_report(self):
        ctx = self.env.context
        data = {
            'ids': ctx.get('active_ids', []),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'report_type': self.report_type,
        }
        data['model'] = 'retention.report.wizard'
        data['form'] = self.read()[0]
        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        return self.env.ref('gn_report_account.action_retention_report').report_action(self, data=data)

    
    @api.constrains('start_date','end_date')
    def validate_dates(self):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError(('The initial date can not be greater than the final.'))
