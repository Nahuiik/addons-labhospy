# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
from dateutil import parser
import pytz


class CashRegisterWizard(models.TransientModel):
    _name = 'cash.register.wizard'
    _description = 'Cash Register Wizard'

    date_from = fields.Date(
        string="Date From",
        default=lambda self: fields.Date.context_today(self),
    )
    date_to = fields.Date(
        string="Date To",
        default=lambda self: fields.Date.context_today(self),
    )
    cashier_ids = fields.Many2many(
        'res.users',
        string="Cajero",
        help="Sin permiso adicional, el arqueo queda limitado al usuario conectado.",
        domain="[('share', '=', False)]",
    )
    can_select_other_cashiers = fields.Boolean(
        compute='_compute_can_select_other_cashiers',
    )

    @api.model
    def _user_can_select_other_cashiers(self):
        return self.env.user.has_group(
            'l10n_hn_cash_register.group_cash_register_other_cashiers'
        )

    def _compute_can_select_other_cashiers(self):
        allowed = self._user_can_select_other_cashiers()
        for rec in self:
            rec.can_select_other_cashiers = allowed

    def _get_report_cashier_ids(self):
        self.ensure_one()
        if self._user_can_select_other_cashiers() and self.cashier_ids:
            return self.cashier_ids.ids
        return [self.env.uid]

    def _restrict_cashiers_if_needed(self, vals):
        if not self._user_can_select_other_cashiers():
            vals['cashier_ids'] = [(6, 0, [self.env.uid])]
        return vals

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'cashier_ids' in fields_list:
            res['cashier_ids'] = [(6, 0, [self.env.uid])]
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._restrict_cashiers_if_needed(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._restrict_cashiers_if_needed(vals)
        return super().write(vals)

    def export_xls(self):
        # Buscar automáticamente todos los diarios de tipo banco y efectivo
        journal_ids = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])])
        if not journal_ids:
            raise ValidationError(_("No se encuentra ningún diario contable de tipo banco o efectivo."))
        context = self.env.context
        datas = {
            'ids': context.get('active_ids', []),
            'date_from': self.date_from,
            'date_to': self.date_to,
            'cashier_ids': self._get_report_cashier_ids(),
        }
        datas['model'] = 'cash.register.wizard'
        datas['form'] = self.read()[0]
        for field in datas['form'].keys():
            if isinstance(datas['form'][field], tuple):
                datas['form'][field] = datas['form'][field][0]
        result = self.report_payment_pdf()
        if not result:
            raise ValidationError(_("No ha tenido ventas ese día."))
        if context.get('xls_export'):
            return self.env.ref('l10n_hn_cash_register.action_cash_register_xls').report_action(self, data=datas)
        if context.get('pdf_export'):
            return self.env.ref('l10n_hn_cash_register.action_cash_register_qweb').report_action(self)
        
    @api.constrains('date_from','date_to')
    def validate_dates(self):
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValidationError(_('The initial date can not be greater than the final.'))
    
    def report_payment_pdf(self):
        account_payment = self.env['account.payment']
        domain = [('payment_type','=','inbound'),('state','in',['posted', 'paid'])]
        if self.date_from:
            domain.append(('date','>=',self.date_from))
        if self.date_to:
            domain.append(('date','<=',self.date_to))
        domain.append(('create_uid', 'in', self._get_report_cashier_ids()))
        
        # Debug: Log search domain
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info('=== Cash Register Search ===')
        _logger.info(f'Domain: {domain}')
        
        obj_payment = account_payment.search(domain)
        _logger.info(f'Payments found: {len(obj_payment)}')
        
        # Debug: Check all payments without filters
        if len(obj_payment) == 0:
            # Check with just payment_type and dates
            domain_minimal = [('payment_type','=','inbound')]
            if self.date_from:
                domain_minimal.append(('date','>=',self.date_from))
            if self.date_to:
                domain_minimal.append(('date','<=',self.date_to))
            
            minimal_payments = account_payment.search(domain_minimal, limit=5)
            _logger.info(f'Total inbound payments (any state): {len(account_payment.search(domain_minimal))}')
            
            if minimal_payments:
                _logger.info('Sample payments found:')
                for p in minimal_payments:
                    _logger.info(f'  {p.name} - State: {p.state} - Date: {p.date} - Amount: {p.amount} - Created by: {p.create_uid.name}')
            
            # Also check what states exist
            all_states = account_payment.search(domain_minimal).mapped('state')
            _logger.info(f'States found in payments: {set(all_states)}')
        _logger.info('=== End Cash Register Search ===')
        obj_create_uid_ids = []
        create_uid_ids = []
        journal_ids = []
        for payment in obj_payment.sorted():
            if payment.create_uid.id in obj_create_uid_ids:
                invoice_ids = []
                for invoice_id in payment.reconciled_invoice_ids:
                    invoice_ids.append({
                        'id': invoice_id.id,
                        'name' : invoice_id.name,
                        'state' : invoice_id.state,
                        'amount_total' : invoice_id.amount_total,
                        'amount_residual' : invoice_id.amount_residual,
                    })
                vals = {
                    'id' : payment.id,
                    'date_payment' : self.change_format(str(payment.date)),
                    'number_payment' : payment.name,
                    'journal_id' : payment.journal_id.name,
                    'invoice_ids' : invoice_ids,
                    'state' : payment.state,
                    'amount' : payment.amount,
                }
                create_uid_ids[obj_create_uid_ids.index(payment.create_uid.id)]['lines_users'].append(vals)
            else:
                obj_create_uid_ids.append(payment.create_uid.id)
                invoice_ids = []
                for invoice_id in payment.reconciled_invoice_ids:
                    invoice_ids.append({
                        'id': invoice_id.id,
                        'name' : invoice_id.name,
                        'state' : invoice_id.state,
                        'amount_total' : invoice_id.amount_total,
                        'amount_residual' : invoice_id.amount_residual,
                    })
                vals = {
                    'id' : payment.id,
                    'date_payment' : self.change_format(str(payment.date)),
                    'number_payment' : payment.name,
                    'journal_id' : payment.journal_id.name,
                    'invoice_ids' : invoice_ids,
                    'state' : payment.state,
                    'amount' : payment.amount,
                }
                create_uid_ids.append({
                    'id' : payment.create_uid.id,
                    'name': payment.create_uid.name,
                    'lines_users':[vals],
                    'company':self.env.user.company_id.name,
                    'date_from' : self.date_from,
                    'date_to' : self.date_to,
                })
        return create_uid_ids

    def get_pending_invoice_sections_for_pdf(self, user_id):
        """Mismos criterios que el Excel: facturas abiertas y parciales del cajero en el rango."""
        if not user_id:
            return {'open_invoice': [], 'partial_invoice': []}
        report = self.env['report.l10n_hn_cash_register.cash_register_xls.xlsx']
        info_list, _dummy = report.get_invoices(self.date_from, self.date_to, [user_id])
        for block in info_list:
            if block.get('cashier_id') == user_id:
                return {
                    'open_invoice': list(block.get('open_invoice') or []),
                    'partial_invoice': list(block.get('partial_invoice') or []),
                }
        return {'open_invoice': [], 'partial_invoice': []}

    def returns_journal_ids(self,user_ids):
        account_payment = self.env['account.payment']
        domain = [('payment_type','=','inbound'),('state','in',['posted','paid','cancel'])]
        if self.date_from:
            domain.append(('date','>=',self.date_from))
        if self.date_to:
            domain.append(('date','<=',self.date_to))
        domain.append(('create_uid','in',[user_ids]))
        obj_payment = account_payment.search(domain)
        journal_ids =[]
        obj_journal_ids =[]
        for payment in obj_payment.sorted():
            if payment.journal_id.id in obj_journal_ids:
                journal_ids[obj_journal_ids.index(payment.journal_id.id)]['amount'] += payment.amount
            else:
                obj_journal_ids.append(payment.journal_id.id)
                journal_ids.append({
                    'id' : payment.journal_id.id,
                    'name' : payment.journal_id.name,
                    'amount' : payment.amount,
                })
        return journal_ids
    
    def returns_cancel_payment(self,user_ids):
        account_payment = self.env['account.payment']
        domain = [('payment_type','=','inbound'),('state','in',['cancel'])]
        if self.date_from:
            domain.append(('date','>=',self.date_from))
        if self.date_to:
            domain.append(('date','<=',self.date_to))
        domain.append(('create_uid','in',[user_ids]))
        obj_payment = account_payment.search(domain)
        payment_cancel =[]
        for payment in obj_payment.sorted():
            payment_cancel.append({
                'id' : payment.id,
                'date_payment' : self.change_format(str(payment.date)),
                'number_payment' : payment.name,
                'journal_id' : payment.journal_id.name,
                'state' : payment.state,
                'amount' : payment.amount,
            })
        return payment_cancel
    def returns_banks_payments(self,user_ids):
        account_payment = self.env['account.payment']
        # Filtrar por diarios de tipo banco y efectivo automáticamente
        journal_ids = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])]).ids
        domain = [('payment_type','=','inbound'),('state','in',['cancel','posted','paid']),('journal_id','in',journal_ids)]
        if self.date_from:
            domain.append(('date','>=',self.date_from))
        if self.date_to:
            domain.append(('date','<=',self.date_to))
        domain.append(('create_uid','in',[user_ids]))
        obj_payment = account_payment.search(domain)
        desposit_banks =[]
        for payment in obj_payment.sorted():
            desposit_banks.append({
                'id' : payment.id,
                'journal_id' : payment.journal_id.name,
                'number_check' : payment.number_check,
                'date_check' : self.change_format(payment.date_check),
                'amount' : payment.amount,
            })
        return desposit_banks


    def change_format(self,date):
        try:
            return datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
        except:
            return date

    #Method to change datetime.now = 2023-01-01 00:00:00 to 01/01/2023 00:00:00 AM 
    def get_format_datetime(self):
        date = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
        try:
            dt = parser.parse(date)
            local_tz = pytz.timezone('America/Tegucigalpa')
            dt_local = dt.astimezone(local_tz)
            hour = dt_local.strftime('%I')
            seconds = dt_local.strftime('%S ')
            am_pm = 'AM' if int(dt_local.strftime('%H')) < 12 else 'PM'
            formatted_date = dt_local.strftime('%d/%m/%Y ') + hour +':'+ dt_local.strftime('%M') + ':'+ seconds + am_pm
            return formatted_date
        except:
            return date
        
    
