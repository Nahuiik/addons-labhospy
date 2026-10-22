# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    gn_customer_cxc_type = fields.Selection(
        selection=[
            ('invoice', 'Factura'),
            ('refund', 'Nota de credito'),
            ('opening', 'Saldo CxC'),
        ],
        string='Tipo CxC',
        compute='_compute_gn_customer_cxc_type',
    )
    gn_customer_days_to_due = fields.Integer(
        string='Dias para vencer',
        compute='_compute_gn_customer_days_to_due',
    )

    @api.depends('move_id.move_type')
    def _compute_gn_customer_cxc_type(self):
        mapping = {
            'out_invoice': 'invoice',
            'out_refund': 'refund',
            'entry': 'opening',
        }
        for line in self:
            line.gn_customer_cxc_type = mapping.get(line.move_id.move_type)

    @api.depends('date_maturity', 'move_id.invoice_date_due', 'move_id.date',
                 'move_id.move_type', 'amount_residual', 'reconciled',
                 'parent_state', 'account_id.account_type')
    def _compute_gn_customer_days_to_due(self):
        today = fields.Date.context_today(self)
        for line in self:
            if (line.account_id.account_type != 'asset_receivable'
                    or line.reconciled or line.amount_residual <= 0
                    or line.parent_state != 'posted'):
                line.gn_customer_days_to_due = 0
                continue
            ref_date = line.date_maturity
            if not ref_date and line.move_id.move_type in (
                    'out_invoice', 'out_refund'):
                ref_date = line.move_id.invoice_date_due
            if not ref_date:
                ref_date = line.move_id.date
            line.gn_customer_days_to_due = (ref_date - today).days if ref_date else 0
