from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class reportWzardDiseases(models.TransientModel):
    _name = 'report.wzard.payroll.diseases'
    _description = 'Report Wzard Payroll for Project'
    
    date_from = fields.Date(string='Fecha de Inicio')
    date_to = fields.Date(string="Fecha de Fin")

    def get_print_report(self):
        vals = {
            'date_from': self.date_from,
            'date_to': self.date_to
        }
        data = vals
        data['model'] = 'report.wzard.payroll.diseases'
        data['form'] = self.read()[0]
        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        return self.env.ref('l10n_hn_hr_recruitment.action_payroll_report_diseases_xls').report_action(self, data=data)
    #@api.constrains('payroll_ids')
    # def validated_payroll(self):
    #     if not self.payroll_ids:
    #         raise ValidationError(_('Seleccione una Nómina.'))