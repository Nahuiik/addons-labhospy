from odoo import models, fields, api, _


class BanksReports(models.TransientModel):
    _name = 'banks.reports'
    _description = 'banks reports'

    transaction_type = fields.Selection([('check', 'Cheque'),('deposit', 'Deposit'),('debit', 'Debits'),('credit', 'Credits'),('card_settlement','POS Settlements'),('tbb','Transfer between banks'),('wire_transfer','Wire Transfer')], string="Transaction Type", default='check',required=True)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    
    def action_print_report(self):
        for rec in self:
            data = {'wizard_id': self.id,
                    'other': True,
                    'start_date': self.start_date,
                    'end_date': self.end_date}
            data['model'] = 'bank.report.wizard'
            data['form'] = self.read()[0]
            for field in data['form'].keys():
                if isinstance(data['form'][field], tuple):
                    data['form'][field] = data['form'][field][0]
            if self.transaction_type == 'check':
                return self.env.ref('gn_banks.action_check_report_xls').report_action(
                    self, data=data)
            elif self.transaction_type == 'deposit':
                return self.env.ref('gn_banks.action_deposit_report_xls').report_action(
                    self, data=data)
            elif self.transaction_type == 'debit':
                return self.env.ref('gn_banks.action_debit_report_xls').report_action(
                    self, data=data)
            elif self.transaction_type == 'credit':
                return self.env.ref('gn_banks.action_credit_report_xls').report_action(
                    self, data=data)
            elif self.transaction_type == 'card_settlement':
                return self.env.ref('gn_banks.action_card_settlement_report_xls').report_action(
                    self, data=data)
            elif self.transaction_type == 'tbb':
                return self.env.ref('gn_banks.action_transfer_banks_report_xls').report_action(
                    self, data=data)
            elif self.transaction_type == 'wire_transfer':
                return self.env.ref('gn_banks.action_wire_transfer_report_xls').report_action(
                    self, data=data)