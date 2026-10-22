# -*- coding: utf-8 -*-
#################################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2018-Today Ascetic Business Solution <www.asceticbs.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#################################################################################

from odoo import api, fields, models, _

class InvoiceOutstanding(models.TransientModel):
    _name = "invoice.outstanding"

    start_date = fields.Datetime(string='From Date', required='1', help='select start date')
    end_date = fields.Datetime(string='To Date', required='1', help='select end date')
    partner_id = fields.Many2one('res.users', string='Cajero')
    total_amount_due = fields.Integer(string='Total Outstanding Amount')
    date = fields.Char('')
    s_date = fields.Char('')
    e_date = fields.Char('')
    print_f = fields.Boolean("Imprimir Facturas de Credito")
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.user.company_id,
        required=False,
        string="Company",
    )

    @api.multi
    def check_report(self):
        data = {}
        data['form'] = self.read(['start_date', 'end_date', 'partner_id'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['start_date', 'end_date', 'partner_id'])[0])
        return self.env.ref('gn_cash_register.action_customer_invoice_outstanding').report_action(self, data=data, config=False)


