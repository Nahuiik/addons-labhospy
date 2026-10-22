# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosCommissionReportWizard(models.TransientModel):
    _name = 'pos.commission.report.wizard'
    _description = 'Wizard para Reporte de Comisiones POS'

    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=fields.Date.context_today
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.context_today
    )
    card_agreement_ids = fields.Many2many(
        'card.agreement',
        string='Convenios de Tarjeta',
        help='Dejar vacío para incluir todos los convenios'
    )
    journal_ids = fields.Many2many(
        'account.journal',
        string='Diarios',
        domain="[('type', '=', 'bank'), ('is_credit_card', '=', True)]",
        help='Dejar vacío para incluir todos los diarios de tarjeta'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )

    def _get_report_data(self):
        """Obtener los datos del reporte"""
        self.ensure_one()
        
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', 'in', ('posted', 'paid', 'reconciled')),  # Incluir pagos publicados y conciliados
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
            ('company_id', '=', self.company_id.id),
        ]
        
        if self.card_agreement_ids:
            domain.append(('card_agreement_id', 'in', self.card_agreement_ids.ids))
        else:
            # Incluir pagos con convenio asignado
            domain.append(('card_agreement_id', '!=', False))
        
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        
        # Buscar todos los pagos que cumplan los criterios básicos
        payments = self.env['account.payment'].search(domain, order='date, card_agreement_id, payment_method_type, months')
        
        # Filtrar después para incluir solo los que tienen método de pago válido (no 'none' ni False)
        payments = payments.filtered(lambda p: p.payment_method_type and p.payment_method_type != 'none')
        
        # Debug: Log para verificar qué pagos se encontraron
        _logger.info("Reporte POS Comisiones - Pagos encontrados: %d", len(payments))
        for payment in payments[:10]:  # Log de los primeros 10 pagos
            _logger.info("Pago encontrado: %s - Estado: %s - Método: %s - Convenio: %s - Meses: %s", 
                       payment.name, payment.state, payment.payment_method_type, 
                       payment.card_agreement_id.name if payment.card_agreement_id else 'Sin convenio',
                       payment.months)
        
        # Agrupar por convenio y tipo de método
        data = {}
        totals = {
            'total_amount': 0.0,
            'total_without_vat': 0.0,
            'total_vat': 0.0,
            'total_commission': 0.0,
            'total_commission_vat': 0.0,
            'total_retention': 0.0,
            'total_deductions': 0.0,
            'total_to_receive': 0.0,
            'payment_count': 0,
        }
        
        for payment in payments:
            # Recalcular campos computados si están en 0 o no están calculados
            # Esto asegura que los pagos antiguos también tengan valores correctos
            if not payment.commission_percentage or payment.commission_percentage == 0:
                payment._compute_commission_percentage()
            if not payment.amount_without_vat or payment.amount_without_vat == 0:
                payment._compute_deduction_details()
            
            agreement_name = payment.card_agreement_id.name or 'Sin Convenio'
            if agreement_name not in data:
                data[agreement_name] = {
                    'agreement': payment.card_agreement_id,
                    'lines': [],
                    'subtotals': {
                        'amount': 0.0,
                        'without_vat': 0.0,
                        'vat': 0.0,
                        'commission': 0.0,
                        'commission_vat': 0.0,
                        'retention': 0.0,
                        'deductions': 0.0,
                        'to_receive': 0.0,
                        'count': 0,
                    }
                }
            
            # Obtener valores
            months_int = payment._get_months_int() if hasattr(payment, '_get_months_int') else 0
            method_label = dict(payment._fields['payment_method_type'].selection).get(payment.payment_method_type, payment.payment_method_type)
            
            # Asegurar que los valores estén calculados
            amount_without_vat = payment.amount_without_vat or 0.0
            vat_amount = payment.vat_amount or 0.0
            commission_amount = payment.commission_amount or 0.0
            commission_vat_amount = payment.commission_vat_amount or 0.0
            retention_amount = payment.retention_amount or 0.0
            total_deductions = payment.total_deductions or 0.0
            amount_to_receive = payment.amount_to_receive or payment.amount or 0.0
            
            line = {
                'payment': payment,
                'date': payment.date,
                'name': payment.name,
                'partner': payment.partner_id.name or '',
                'amount': payment.amount,
                'method_type': method_label,
                'months': months_int,
                'commission_pct': payment.commission_percentage or 0.0,
                'amount_without_vat': amount_without_vat,
                'vat_amount': vat_amount,
                'commission_amount': commission_amount,
                'commission_vat_amount': commission_vat_amount,
                'retention_amount': retention_amount,
                'total_deductions': total_deductions,
                'amount_to_receive': amount_to_receive,
            }
            
            data[agreement_name]['lines'].append(line)
            
            # Subtotales por convenio (usar valores de la línea que ya están calculados)
            data[agreement_name]['subtotals']['amount'] += line['amount']
            data[agreement_name]['subtotals']['without_vat'] += line['amount_without_vat']
            data[agreement_name]['subtotals']['vat'] += line['vat_amount']
            data[agreement_name]['subtotals']['commission'] += line['commission_amount']
            data[agreement_name]['subtotals']['commission_vat'] += line['commission_vat_amount']
            data[agreement_name]['subtotals']['retention'] += line['retention_amount']
            data[agreement_name]['subtotals']['deductions'] += line['total_deductions']
            data[agreement_name]['subtotals']['to_receive'] += line['amount_to_receive']
            data[agreement_name]['subtotals']['count'] += 1
            
            # Totales generales (usar valores de la línea que ya están calculados)
            totals['total_amount'] += line['amount']
            totals['total_without_vat'] += line['amount_without_vat']
            totals['total_vat'] += line['vat_amount']
            totals['total_commission'] += line['commission_amount']
            totals['total_commission_vat'] += line['commission_vat_amount']
            totals['total_retention'] += line['retention_amount']
            totals['total_deductions'] += line['total_deductions']
            totals['total_to_receive'] += line['amount_to_receive']
            totals['payment_count'] += 1
        
        return {
            'wizard': self,
            'data': data,
            'totals': totals,
            'company': self.company_id,
            'date_from': self.date_from,
            'date_to': self.date_to,
        }

    def action_print_excel(self):
        """Generar reporte en Excel"""
        self.ensure_one()
        if not self.date_from or not self.date_to:
            raise UserError(_('Debe seleccionar las fechas del reporte.'))
        
        return self.env.ref('gn_payment_extra.action_pos_commission_report_xls').report_action(self)

    def action_print_pdf(self):
        """Generar reporte en PDF"""
        self.ensure_one()
        if not self.date_from or not self.date_to:
            raise UserError(_('Debe seleccionar las fechas del reporte.'))
        
        return self.env.ref('gn_payment_extra.action_pos_commission_report_pdf').report_action(self)
