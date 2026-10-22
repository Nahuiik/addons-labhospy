from odoo import fields, models, api
from odoo.exceptions import UserError

class SupplierAccountState(models.TransientModel):
    _name = 'supplier.account.state'
    _description = 'Supplier Account State'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    
    def action_generate_report_supplier(self):
        vals = {
            'start_date': self.start_date,
            'end_date': self.end_date,
        }
        data = vals
        data['model'] = 'supplier.account.state'
        data['form'] = self.read()[0]
        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        return self.env.ref('gn_report_account.action_supplier_account_state_xls').report_action(self, data=data)