# -*- coding: utf-8 -*-
"""Asistente de regularización ISV (904, casillas 21 y 31): asiento en borrador; validar con SAR antes de publicar."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HnIsvClosingWizard(models.TransientModel):
    _name = 'hn.isv.closing.wizard'
    _description = 'Cierre ISV Honduras (borrador)'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)
    year = fields.Integer(
        required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection(
        [
            ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
            ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
            ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'),
            ('12', 'Diciembre'),
        ],
        default=lambda self: str(fields.Date.today().month),
        required=True,
    )
    journal_id = fields.Many2one(
        'account.journal', string='Diario',
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    date = fields.Date(
        string='Fecha del asiento',
        required=True,
        default=lambda self: fields.Date.today(),
    )
    ref = fields.Char(
        string='Referencia',
        default='Cierre ISV',
    )

    casilla_21 = fields.Monetary(
        string='Total etiquetado cas. 21 (débito fiscal)',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    casilla_31 = fields.Monetary(
        string='Total etiquetado cas. 31 (crédito fiscal)',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    suggested_difference = fields.Monetary(
        string='Sugerido (21 − 31)',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    amount = fields.Monetary(
        string='Importe del asiento',
        currency_field='currency_id',
        required=True,
        help='Por defecto casilla 21 − 31 según el motor 904. Ajustar tras revisión contable.',
    )

    debit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta debe',
        required=True,
        check_company=True,
        domain="[('company_ids', 'parent_of', company_id)]",
    )
    credit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta haber',
        required=True,
        check_company=True,
        domain="[('company_ids', 'parent_of', company_id)]",
    )

    @api.depends('year', 'month', 'company_id')
    def _compute_totals(self):
        iso = self.env['hn.isv.report']
        for wiz in self:
            data = iso.get_data_hn_isv(wiz.year, int(wiz.month), company=wiz.company_id)
            by_c = {x['casilla']: x['balance'] for x in data['casillas']}
            c21 = float(by_c.get(21, 0.0))
            c31 = float(by_c.get(31, 0.0))
            wiz.casilla_21 = c21
            wiz.casilla_31 = c31
            wiz.suggested_difference = c21 - c31

    @api.onchange('year', 'month', 'company_id')
    def _onchange_period_amount(self):
        data = self.env['hn.isv.report'].get_data_hn_isv(
            self.year, int(self.month), company=self.company_id)
        by_c = {x['casilla']: x['balance'] for x in data['casillas']}
        self.amount = float(by_c.get(21, 0.0)) - float(by_c.get(31, 0.0))
        comp = self.company_id or self.env.company
        if comp.hn_isv_closing_journal_id:
            self.journal_id = comp.hn_isv_closing_journal_id
        if comp.hn_isv_closing_debit_account_id:
            self.debit_account_id = comp.hn_isv_closing_debit_account_id
        if comp.hn_isv_closing_credit_account_id:
            self.credit_account_id = comp.hn_isv_closing_credit_account_id

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        comp = self.env.company
        if vals.get('company_id'):
            comp = self.env['res.company'].browse(vals['company_id'])
        y = vals.get('year') or fields.Date.today().year
        m = int(vals.get('month') or fields.Date.today().month)
        data = self.env['hn.isv.report'].get_data_hn_isv(y, m, company=comp)
        by_c = {x['casilla']: x['balance'] for x in data['casillas']}
        if 'amount' in fields_list:
            vals['amount'] = float(by_c.get(21, 0.0)) - float(by_c.get(31, 0.0))
        if 'journal_id' in fields_list and comp.hn_isv_closing_journal_id:
            vals['journal_id'] = comp.hn_isv_closing_journal_id.id
        if 'debit_account_id' in fields_list and comp.hn_isv_closing_debit_account_id:
            vals['debit_account_id'] = comp.hn_isv_closing_debit_account_id.id
        if 'credit_account_id' in fields_list and comp.hn_isv_closing_credit_account_id:
            vals['credit_account_id'] = comp.hn_isv_closing_credit_account_id.id
        return vals

    def action_create_draft_move(self):
        self.ensure_one()
        amt = abs(self.amount)
        if amt < 0.0001:
            raise UserError(_('El importe debe ser distinto de cero.'))
        if self.amount < 0:
            debit_acc = self.credit_account_id
            credit_acc = self.debit_account_id
        else:
            debit_acc = self.debit_account_id
            credit_acc = self.credit_account_id
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.ref,
            'company_id': self.company_id.id,
            'line_ids': [
                (0, 0, {
                    'account_id': debit_acc.id,
                    'name': self.ref,
                    'debit': amt,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': credit_acc.id,
                    'name': self.ref,
                    'debit': 0.0,
                    'credit': amt,
                }),
            ],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }
