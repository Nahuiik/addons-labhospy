# -*- coding: utf-8 -*-
"""
Modelo para reportes de anticipos de clientes.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class AccountAdvanceReport(models.TransientModel):
    """Wizard para generar reportes de anticipos"""
    _name = 'account.advance.report.wizard'
    _description = 'Wizard de Reporte de Anticipos'

    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.today
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente/Proveedor'
    )
    partner_type = fields.Selection([
        ('customer', 'Cliente'),
        ('supplier', 'Proveedor'),
    ], string='Tipo de Partner', default='customer', required=True)
    
    @api.onchange('partner_type')
    def _onchange_partner_type(self):
        """Limpiar partner_id cuando cambia el tipo"""
        self.partner_id = False
        return {
            'domain': {
                'partner_id': [
                    ('customer_rank', '>', 0) if self.partner_type == 'customer' else ('supplier_rank', '>', 0)
                ]
            }
        }
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda'
    )
    state_filter = fields.Selection([
        ('all', 'Todos'),
        ('available', 'Con Saldo Disponible'),
        ('applied', 'Aplicados Parcialmente'),
        ('fully_applied', 'Totalmente Aplicados'),
        ('unapplied', 'Sin Aplicar'),
    ], string='Estado', default='all')

    def action_generate_report(self):
        """Genera el reporte de anticipos"""
        self.ensure_one()
        
        domain = [
            ('is_advance', '=', True),
            ('partner_type', '=', self.partner_type),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ]
        
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        
        if self.currency_id:
            domain.append(('currency_id', '=', self.currency_id.id))
        
        payments = self.env['account.payment'].search(domain)
        
        # Filtrar por estado
        if self.state_filter == 'available':
            payments = payments.filtered(lambda p: p.advance_available_amount > 0)
        elif self.state_filter == 'applied':
            payments = payments.filtered(lambda p: p.advance_applied_total > 0 and p.advance_available_amount > 0)
        elif self.state_filter == 'fully_applied':
            payments = payments.filtered(lambda p: p.advance_available_amount == 0 and p.advance_applied_total > 0)
        elif self.state_filter == 'unapplied':
            payments = payments.filtered(lambda p: p.advance_applied_total == 0)
        
        # Preparar datos para el reporte
        report_data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'partner_name': self.partner_id.name if self.partner_id else 'Todos los clientes',
            'company_name': self.company_id.name,
            'currency_name': self.currency_id.name if self.currency_id else 'Todas las monedas',
            'total_received': sum(payments.mapped('amount')),
            'total_applied': sum(payments.mapped('advance_applied_total')),
            'total_available': sum(payments.mapped('advance_available_amount')),
            'count': len(payments),
            'payments': []
        }
        
        for payment in payments:
            report_data['payments'].append({
                'name': payment.name,
                'partner': payment.partner_id.name,
                'date': payment.date,
                'amount': payment.amount,
                'applied': payment.advance_applied_total,
                'available': payment.advance_available_amount,
                'state': dict(payment._fields['state'].selection)[payment.state],
                'currency': payment.currency_id.name,
            })
        
        # Crear registros de resultado
        result_model = self.env['account.advance.report.result']
        # Limpiar resultados anteriores del wizard
        result_model.search([('wizard_id', '=', self.id)]).unlink()
        
        # Crear resultados
        for payment_data in report_data['payments']:
            payment = self.env['account.payment'].browse(
                self.env['account.payment'].search([
                    ('name', '=', payment_data['name']),
                    ('partner_id.name', '=', payment_data['partner'])
                ], limit=1).id
            )
            if payment:
                result_model.create({
                    'wizard_id': self.id,
                    'payment_id': payment.id,
                    'partner_id': payment.partner_id.id,
                    'date': payment_data['date'],
                    'amount': payment_data['amount'],
                    'applied': payment_data['applied'],
                    'available': payment_data['available'],
                    'state': payment_data['state'],
                    'currency_id': payment.currency_id.id,
                })
        
        # Crear acción para mostrar el reporte
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reporte de Anticipos'),
            'res_model': 'account.advance.report.result',
            'view_mode': 'list',
            'domain': [('wizard_id', '=', self.id)],
            'context': {'create': False, 'edit': False, 'delete': False},
            'target': 'current',
        }


class AccountAdvanceReportResult(models.TransientModel):
    """Resultados del reporte de anticipos"""
    _name = 'account.advance.report.result'
    _description = 'Resultado de Reporte de Anticipos'
    _order = 'date desc'

    wizard_id = fields.Many2one('account.advance.report.wizard', string='Wizard')
    payment_id = fields.Many2one('account.payment', string='Anticipo')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    date = fields.Date(string='Fecha')
    amount = fields.Monetary(string='Monto Recibido', currency_field='currency_id')
    applied = fields.Monetary(string='Aplicado', currency_field='currency_id')
    available = fields.Monetary(string='Disponible', currency_field='currency_id')
    state = fields.Char(string='Estado')
    currency_id = fields.Many2one('res.currency', string='Moneda')
