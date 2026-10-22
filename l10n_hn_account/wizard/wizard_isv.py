# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

MONTH_GROUP = [('january', 'January'),
               ('february', 'February'),
               ('march', 'March'),
               ('april', 'April'),
               ('may', 'May'),
               ('june', 'June'),
               ('july', 'July'),
               ('august', 'August'),
               ('september', 'September'),
               ('october', 'October'),
               ('november', 'November'),
               ('december', 'December')]

class wizardISVReport(models.TransientModel):
    _name = 'l10n_hn_account.wizard_isv_report'
    _description = 'Description'

    month = fields.Selection(MONTH_GROUP, string="Month")
    fiscal_credit = fields.Float(string="Previous Period Tax Credit")
    pos = fields.Float(string="POS Retained Tax")

    def print_report(self):
        """Call when button 'Get Report' clicked."""
        data = {
            'ids': self.ids,
            'month': self.month,
            'fiscal_credit': self.fiscal_credit,
            'pos': self.pos,
        }
        data['model'] = 'l10n_hn_account.wizard_isv_report'
        data['form'] = self.read()[0]
        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        report = self.env.ref("l10n_hn_account.report_isv").report_action(self, data=data)
        if self.env.context.get('xls_export'):
            return self.env.ref('l10n_hn_account.isv_report_xls').report_action(self, data=data)
        return report
