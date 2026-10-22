# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from datetime import *
import time
from datetime import datetime, timedelta


class BankReconciliation(models.Model):
    _name = 'bank.reconciliation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Bank Reconciliation"
    _order = 'date desc'


    @api.onchange("account_id")
    def onchangemoneda(self):
        if self.account_id:
            if self.account_id.currency_id:
                self.currency_id = self.account_id.currency_id.id
            else:
                if self.company_id:
                    self.currency_id = self.company_id.currency_id.id

    def action_report_xls(self):
        # for rec in self:
        vals = {
            'account_id':self.account_id.id,
            'account_name':self.account_id.name,
            'currency_id':self.currency_id,
            'date':self.date,
            'balance_start':self.balance_start,
            'saldo_final':self.end_balance,
            'name':self.name,
            'conciliacion_line':self.reconciliation_line,
            'state':self.state,
            'difference':self.difference,
            'mes_name':self.month_name,
            'is_conciliado_father':self.is_conciliado_father,
            'id':self.id
        }
        data = vals
        # data = ''
        data['model'] = 'bank.reconciliation'
        data['form'] = self.read()[0]
        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        return self.env.ref('l10n_hn_bank_reconciliation.action_conciliation_report_xls').report_action(self,data=data)

    @api.onchange("date")
    def onchangefecha(self):         
        if self.date:
            varialble_string = datetime.strptime(str(self.date), '%Y-%m-%d').date()
            self.month_name = varialble_string.strftime('%B')
            if self.account_id:
                self.name = self.account_id.name +'/' + self.month_name +'/'+ varialble_string.strftime('%Y')


    company_id = fields.Many2one("res.company", "Compañia", required=True, tracking=True, default=lambda self: self.env.company)
    #('reconcile', '=', True),
    account_id = fields.Many2one("account.account", "Banco", tracking=True, required=True, domain="[('account_type', 'in', ['asset_cash', 'liability_credit_card'])]")
    currency_id = fields.Many2one("res.currency", "Moneda", tracking=True)
    date = fields.Date(string="Fecha Final", help="Effective date for accounting entries", required=True, tracking=True)
    balance_start = fields.Float(string='Balance Start', compute='_compute_balance_start')
    end_balance = fields.Float(string='Saldo Final')
    name = fields.Text(string="Descripción", required=True, tracking=True)
    reconciliation_line = fields.One2many("bank.reconciliation.line", "reconciliation_id", "Detalle de conciliación")
    state = fields.Selection([('draft', 'Borrador'), ('validated', 'Validado'), ('anulated', "Anulado")], string="Estado", default='draft')
    difference = fields.Float(string='Diferencia', compute='_compute_rest_credit')
    month_name = fields.Char("Mes del Año", tracking=True)
    is_conciliado_father = fields.Boolean(string='Conciliado')
    is_state_draft = fields.Boolean(string='Include Draft Status')

    @api.onchange('is_conciliado_father')
    def change_conciliado(self):
        for cont in self:
            for rec in cont.reconciliation_line:
                if cont.is_conciliado_father:
                    rec.is_reconciled = True
                else:
                    rec.is_reconciled = False

    @api.depends('reconciliation_line.debit', 'reconciliation_line.credit', 'end_balance')
    def _compute_rest_credit(self):
        for concil in self:
            debit_line = 0
            credit_line = 0
            for lines in self.reconciliation_line:
                if lines.is_reconciled:
                    if lines.debit > 0.0:
                        debit_line += lines.debit
                    if lines.credit > 0.0:
                        credit_line += lines.credit
            concil.difference = concil.balance_start + debit_line - credit_line- concil.end_balance
            
    @api.depends('end_balance', 'account_id', 'company_id')
    def _compute_balance_start(self):
        for rec in self:
            rec.balance_start = 0.0
            if not rec.account_id or not rec.account_id.id or not rec.company_id:
                continue
            try:
                balance_end = 0
                account_id = rec.account_id.id
                company_id = rec.company_id.id
                # Usar SQL directo para evitar problemas con gts_coa_hierarchy que intercepta el dominio
                self.env.cr.execute("""
                    SELECT id, account_id, date, end_balance
                    FROM bank_reconciliation
                    WHERE account_id = %s
                      AND company_id = %s
                      AND state IN ('validated', 'draft')
                    ORDER BY date
                """, (account_id, company_id))
                results = self.env.cr.dictfetchall()
                if results:
                    # Convertir resultados a registros usando browse
                    conciliation_ids = [r['id'] for r in results]
                    conciliation_bank = self.env['bank.reconciliation'].browse(conciliation_ids)
                    conciliation_bank_neat = sorted(conciliation_bank, key=lambda x: x.date)
                    conciliation_bank_less = min(conciliation_bank, key=lambda x: x.date)
                    if rec.id and rec.id == conciliation_bank_less.id:
                        rec.balance_start = 0
                    else:
                        for conciliation in conciliation_bank_neat:
                            if rec.id and rec.id == conciliation.id and rec.id != conciliation_bank_less.id:
                                rec.balance_start = balance_end
                            balance_end = conciliation.end_balance
            except Exception:
                # Si hay algún error, simplemente dejar balance_start en 0.0
                rec.balance_start = 0.0

    def action_validate(self):
        if not self.reconciliation_line:
            raise UserError(_('No existen movimiento a conciliar') )

        if not round(self.difference, 2) == 0.0:
            raise UserError(_('Existe diferencia en la conicliación, debe de revisar todos los movimientos a conciliar') )

        for mov_conciliar in self.reconciliation_line:
            if mov_conciliar.is_reconciled:
                mov_conciliar.move_id.is_reconciled = True
                mov_conciliar.move_line_id.is_reconciled = True
                mov_conciliar.move_line_id.reconciled = True
                mov_conciliar.move_id.reconciliation_id = self.id

        self.write({'state': 'validated'})

    def action_anulated(self):
        for mov_conciliar in self.reconciliation_line:
            if mov_conciliar.is_reconciled:
                mov_conciliar.move_id.is_reconciled = False
                mov_conciliar.move_line_id.is_reconciled = False
                mov_conciliar.move_line_id.reconciled = False
                mov_conciliar.move_id.reconciliation_id = False

        self.write({'state': 'anulated'})

    def back_draft(self):
        self.write({'state': 'draft'})


    def get_movement(self):
        if self.reconciliation_line:
            self.reconciliation_line.unlink()
        if not self.account_id or not self.company_id:
            return
        domain = [
            ('date', '<=', self.date),
            ('account_id', '=', self.account_id.id),
            ('company_id', '=', self.company_id.id),
            ('is_reconciled', '=', False)
        ]
        if self.is_state_draft:
            domain.append(('move_id.state', 'in', ['posted', 'draft']))
        else:
            domain.append(('move_id.state', '=', 'posted'))
        obj_move_id = self.env["account.move.line"].search(domain)
        for movement in obj_move_id:
            obj_line = self.env["bank.reconciliation.line"]
            vals = {
                'reconciliation_id': self.id,
                'move_id': movement.move_id.id,
                'move_line_id': movement.id,
                'partner_id': movement.partner_id.id,
                'date': movement.date,
                'currency_id': movement.currency_id.id,
                'is_reconciled': False,
                'name': movement.ref,
                #'analytic_id': movement.analytic_id.id,
                'import_coin': movement.amount_currency,
            }
            if movement.debit > 0:
                vals["debit"] = movement.debit
            if movement.credit > 0:
                vals["credit"] = movement.credit

            line_id =  obj_line.create(vals)

class Debitline(models.Model):
    _name = 'bank.reconciliation.line'
    _description = 'Bank Reconciliation Line'

    reconciliation_id = fields.Many2one('bank.reconciliation', 'Conciliación')
    move_id = fields.Many2one("account.move", "Movimiento")
    move_line_id = fields.Many2one("account.move.line", "Linea de movimiento")
    partner_id = fields.Many2one('res.partner', 'Empresa')
    date = fields.Date(string="Fecha", help="Effective date for accounting entries", required=True)
    name = fields.Char('Descripción')
    debit = fields.Float('Debe')
    credit = fields.Float("Haber")
    currency_id = fields.Many2one('res.currency', string='Currency')
    analytic_id = fields.Many2one("account.analytic.account", string="Cuenta Analitica")
    is_reconciled = fields.Boolean("Conciliado")
    import_coin = fields.Float("Importe de moneda")
