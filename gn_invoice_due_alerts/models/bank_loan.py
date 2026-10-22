# -*- coding: utf-8 -*-
import calendar
from datetime import date

from odoo import api, fields, models, _
from odoo.tools.misc import formatLang


class BankLoan(models.Model):
    _name = 'gn.bank.loan'
    _description = 'Prestamo bancario'
    _order = 'bank, loan_number'

    _loan_number_company_uniq = models.Constraint(
        'unique(loan_number, bank, company_id)',
        'El numero de prestamo debe ser unico por banco y compania.',
    )

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compania', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)
    bank = fields.Char(string='Banco', required=True)
    loan_number = fields.Char(string='Numero de prestamo', required=True)
    total_amount = fields.Monetary(string='Monto total')
    monthly_fee = fields.Monetary(string='Cuota mensual', required=True)
    balance = fields.Monetary(string='Saldo')
    rate = fields.Float(string='Tasa (%)', digits=(16, 4))
    payment_day = fields.Integer(
        string='Dia de cuota mensual', required=True,
        help='Dia del mes en que vence la cuota.')
    end_date = fields.Date(string='Fecha finalizacion')
    purpose = fields.Char(string='Destino del prestamo')
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('active', 'Activo'),
        ('paid_off', 'Cancelado'),
    ], string='Estado', compute='_compute_state', store=True)
    debit_ids = fields.One2many('debit.credit', 'loan_id', string='Pagos (debitos)')
    debit_count = fields.Integer(compute='_compute_debit_count')
    next_due_date = fields.Date(
        string='Proximo vencimiento', compute='_compute_due_info', store=True)
    days_to_due = fields.Integer(
        string='Dias para vencer', compute='_compute_due_info', store=True)
    paid_current_month = fields.Boolean(
        string='Cuota del mes pagada', compute='_compute_due_info', store=True)
    due_bucket = fields.Selection([
        ('paid', 'Pagado este mes'),
        ('today', 'Vence hoy'),
        ('due_1_7', 'Por vencer (1-7 dias)'),
        ('due_8_15', 'Por vencer (8-15 dias)'),
        ('overdue', 'Vencida'),
        ('al_dia', 'Al dia'),
    ], string='Semaforo', compute='_compute_due_info', store=True)
    last_payment_date = fields.Date(compute='_compute_last_payment')

    @api.depends('bank', 'loan_number')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s — %s' % (rec.bank or '', rec.loan_number or '')

    @api.depends('balance', 'end_date', 'active')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.active or (rec.balance is not None and rec.balance <= 0):
                rec.state = 'paid_off'
            elif rec.end_date and rec.end_date < today:
                rec.state = 'paid_off'
            else:
                rec.state = 'active'

    def _compute_debit_count(self):
        for rec in self:
            rec.debit_count = len(rec.debit_ids)

    @api.model
    def _due_date_in_month(self, year, month, payment_day):
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(payment_day, last_day))

    @api.model
    def _next_due_date(self, payment_day, end_date, today):
        if end_date and end_date < today:
            return False
        candidate = self._due_date_in_month(today.year, today.month, payment_day)
        if candidate >= today:
            if end_date and candidate > end_date:
                return False
            return candidate
        month = today.month + 1
        year = today.year
        if month > 12:
            month = 1
            year += 1
        candidate = self._due_date_in_month(year, month, payment_day)
        if end_date and candidate > end_date:
            return False
        return candidate

    def _is_paid_in_month(self, year, month):
        self.ensure_one()
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return bool(self.debit_ids.filtered(
            lambda d: d.state == 'validated' and start <= d.date <= end))

    @api.depends('payment_day', 'end_date', 'debit_ids.state', 'debit_ids.date')
    def _compute_due_info(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == 'paid_off':
                rec.next_due_date = False
                rec.days_to_due = 0
                rec.paid_current_month = True
                rec.due_bucket = 'paid'
                continue
            current_due = rec._due_date_in_month(
                today.year, today.month, rec.payment_day)
            paid = rec._is_paid_in_month(today.year, today.month)
            rec.paid_current_month = paid
            if paid:
                nxt = rec._next_due_date(rec.payment_day, rec.end_date, today)
                rec.next_due_date = nxt
                rec.days_to_due = (nxt - today).days if nxt else 0
                rec.due_bucket = 'paid'
                continue
            if today > current_due:
                rec.next_due_date = current_due
                rec.days_to_due = (current_due - today).days
                rec.due_bucket = 'overdue'
            else:
                rec.next_due_date = current_due
                rec.days_to_due = (current_due - today).days
                if rec.days_to_due == 0:
                    rec.due_bucket = 'today'
                elif rec.days_to_due <= 7:
                    rec.due_bucket = 'due_1_7'
                elif rec.days_to_due <= 15:
                    rec.due_bucket = 'due_8_15'
                else:
                    rec.due_bucket = 'al_dia'

    @api.depends('debit_ids.state', 'debit_ids.date')
    def _compute_last_payment(self):
        for rec in self:
            debits = rec.debit_ids.filtered(lambda d: d.state == 'validated')
            rec.last_payment_date = max(debits.mapped('date')) if debits else False

    def action_register_debit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar debito bancario'),
            'res_model': 'debit.credit',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_move_type': 'debit',
                'default_total': self.monthly_fee,
                'default_description': _('Cuota prestamo %s - %s') % (
                    self.loan_number, self.bank),
                'default_loan_id': self.id,
                'default_date': fields.Date.context_today(self),
                'default_company_id': self.company_id.id,
            },
        }

    def action_view_debits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pagos del prestamo'),
            'res_model': 'debit.credit',
            'view_mode': 'list,form',
            'domain': [('loan_id', '=', self.id)],
            'context': {'default_loan_id': self.id, 'default_move_type': 'debit'},
        }
