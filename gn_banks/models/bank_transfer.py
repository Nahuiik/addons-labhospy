# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo import Command
from odoo.exceptions import UserError


class BankTransfer(models.Model):
    _name = 'bank.transfer'
    _description = 'Bank Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'gn.banks.document.journal.mixin', 'gn.banks.manual_payment.mixin', 'gn.banks.usd_rate.mixin']
    _order = 'name desc'
    
    name = fields.Char(string="Name", default="/", copy=False, tracking=4)
    dummy_name = fields.Char(compute='_compute_sequence_preview', string="Dummy Name")
    error_msg = fields.Char(compute='_compute_sequence_preview', string="Error Message")
    move_type = fields.Selection([('transference_banks', "Bank Transfer")], string="Move Type",
                                 default='transference_banks', required=True)
    journal_id= fields.Many2one("account.journal", "Journal", required=True,
                                domain="[('type', 'in',['bank'])]", tracking=10)
    dest_journal_id= fields.Many2one("account.journal", "Transfer To", required=True,
                                     domain="[('type', 'in',['bank'])]",
                                     tracking=15)
    date = fields.Date(string="Date", help="Effective Transaction Date", required=True, tracking=20)
    total = fields.Float(string='Total', required=True, tracking=25)
    description = fields.Text(string="Description", required=True, tracking=30)
    currency_id = fields.Many2one("res.currency", "Currency", domain=[('active', '=', True)],
                                  default=lambda self: self.env.company.currency_id, 
                                  tracking=35, required=True)
    company_id = fields.Many2one("res.company", "Company", 
                                 default=lambda self: self.env.company,
                                 required=True, tracking=40)
    state = fields.Selection([('draft', 'Draft'), ('validated', 'Validated'), ('cancel', "Canceled")],
                             string="State", default='draft', copy=False, tracking=45)
    currency_rate = fields.Float(
        "Currency Rate", digits=(12, 4), tracking=50, default=1.0, readonly=True,
    )
    move_id = fields.Many2one('account.move', 'Apunte Contable', readonly=True, copy=False)
    #es_moneda_base = fields.Boolean("Es moneda base")
    # Campos analíticos
    analytic_distribution = fields.Json(
        string='Distribución Analítica',
        copy=False,
        default={},
        help="Analytic distribution for this record"
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        check_company=True,
        help="Analytic account for this record"
    )
    analytic_precision = fields.Integer(
        string='Analytic Precision',
        related='company_id.currency_id.decimal_places',
        readonly=True,
        help="Precision for analytic amounts"
    )

    @api.onchange("journal_id")
    def change_journal_id(self):
        if self.journal_id:
            if self.journal_id.currency_id:
                self.currency_id = self.journal_id.currency_id.id
            else:
                self.currency_id = self.company_id.currency_id.id
                
    @api.onchange("currency_id")
    def change_currency_id(self):
        if self.currency_id:
            if self.currency_id != self.company_id.currency_id:
                self.currency_rate = self.currency_id.with_context(date=self.date).rate
            else:
                self.currency_rate = 1
                
    @api.depends('journal_id', 'move_type')
    def _compute_sequence_preview(self):
        for rec in self:
            rec.dummy_name = False
            rec.error_msg = False
            if not rec.journal_id or not rec.move_type:
                continue
            sequence = self.env['ir.sequence'].search([
                ('move_type', '=', rec.move_type),
                ('journal_id', '=', rec.journal_id.id),
            ], limit=1)
            if not sequence:
                rec.error_msg = _(
                    "No sequence configuration found for journal '%s', move type '%s'",
                    rec.journal_id.display_name,
                    rec.move_type,
                )
            else:
                rec.dummy_name = sequence.get_next_char(sequence.number_next_actual)
              
    @api.onchange('journal_id', 'move_type')
    def change_journal_move_type(self):
        if self.journal_id and self.move_type:
            self._compute_sequence_preview()
            
    def unlink(self):
        for rec in self:
            if rec.name != '/' and not self._context.get('force_delete'):
                raise UserError(_("You cannot delete an record which has been validated once."))
        return super(BankTransfer, self).unlink()
    
    def action_cancel(self):
        if not self.move_id:
            return
        self.move_id.button_draft()
        self.move_id.button_cancel()
        self.state = 'cancel'
    
    def action_set_to_draft(self):
        if self.state == 'cancel':
            self.state = 'draft'
            self.move_id.button_draft() 
            
    def action_validate(self):
        if self.total <= 0:
            raise UserError(_("Negative or zero total is not allowed"))
        
        if not self.currency_rate:
            self.currency_rate = 1.0
        if self.currency_id and self.currency_id != self.company_id.currency_id:
            self.currency_rate = self.currency_id.with_context(date=self.date).rate

        if not self.move_id:
            sequence_id = self.env['ir.sequence'].search([
                ('move_type', '=', self.move_type),
                ('journal_id', '=', self.journal_id.id),
            ], limit=1)
            if not sequence_id:
                raise UserError(
                    "No sequence configuration found for journal '%s', move type '%s'" %
                    (self.journal_id.display_name, self.move_type)
                )
            self.name = sequence_id.next_by_id()

        move = self.create_line_move()
        self.move_id = move.id
        self.state = 'validated'
        
        
    def create_line_move(self):
        company_currency = self.company_id.currency_id
        if not self.move_id:
            values = {
                'journal_id': self.journal_id.id,
                'date': self.date,
                'ref': self.description,
                'state': 'draft',
                'name': self.name,
                'sequence_generated': True,
                'move_type': 'entry',
            }
            move = self.env['account.move'].create(values)
        else:
            move = self.move_id
            if move.state != 'draft':
                raise UserError(_("Linked move is not in draft state. Please check."))
            move.write({'date': self.date, 'ref': self.description})

        source_account = self._get_manual_payment_account_from_journal(
            self.journal_id, is_outbound=True
        )
        source_account_id = source_account.id if source_account else False

        dest_account = self._get_manual_payment_account_from_journal(
            self.dest_journal_id, is_outbound=False
        )
        dest_account_id = dest_account.id if dest_account else False

        commands = [Command.clear()]

        credit_vals = {
            'name': self.description,
            'account_id': source_account_id,
            'credit': self.total * self.currency_rate,
            'debit': 0.0,
            'date': self.date,
        }
        # Agregar campos analíticos
        if self.analytic_distribution:
            credit_vals['analytic_distribution'] = self.analytic_distribution
        elif self.analytic_account_id:
            credit_vals['analytic_account_id'] = self.analytic_account_id.id
        if self.currency_id != company_currency:
            credit_vals.update({
                'currency_id': self.currency_id.id,
                'amount_currency': -self.total,
            })
        commands.append(Command.create(credit_vals))

        debit_vals = {
            'name': self.description,
            'account_id': dest_account_id,
            'credit': 0.0,
            'debit': self.total * self.currency_rate,
            'date': self.date,
        }
        # Agregar campos analíticos
        if self.analytic_distribution:
            debit_vals['analytic_distribution'] = self.analytic_distribution
        elif self.analytic_account_id:
            debit_vals['analytic_account_id'] = self.analytic_account_id.id
        if self.currency_id != company_currency:
            debit_vals.update({
                'currency_id': self.currency_id.id,
                'amount_currency': self.total,
            })
        commands.append(Command.create(debit_vals))

        move.with_context(check_move_validity=False).write({'line_ids': commands})
        move.action_post()
        return move

    
    
        
