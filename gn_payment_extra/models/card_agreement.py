# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CardAgreement(models.Model):
    _name = 'card.agreement'
    _description = 'Convenio de Tarjetas'
    _order = 'name'

    name = fields.Char(
        string='Nombre del Convenio',
        required=True,
        help='Nombre del convenio de tarjetas (ej: Banco Agrícola, Credomatic, etc.)'
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain="[('type', '=', 'bank'), ('is_credit_card', '=', True)]",
        help='Diario tipo banco asociado a este convenio de tarjetas'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        help='Compañía a la que pertenece este convenio'
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Indica si el convenio está activo'
    )
    agreement_line_ids = fields.One2many(
        'card.agreement.line',
        'card_agreement_id',
        string='Líneas de Comisión',
        help='Matriz de comisiones por tipo de método de pago'
    )

    _journal_unique = models.Constraint(
        'unique(journal_id, company_id)',
        'Ya existe un convenio para este diario en esta compañía',
    )

    @api.constrains('agreement_line_ids')
    def _check_agreement_lines(self):
        """Validar que haya al menos una línea y que no haya duplicados por tipo de método"""
        for agreement in self:
            if not agreement.agreement_line_ids:
                raise ValidationError(_('Debe agregar al menos una línea de comisión al convenio.'))
            
            # Verificar duplicados - permitir múltiples extra_financiamiento con diferentes meses
            seen_combinations = set()
            for line in agreement.agreement_line_ids:
                if line.payment_method_type == 'extra_financiamiento':
                    # Para extra_financiamiento, la combinación única es tipo + meses
                    key = (line.payment_method_type, line.months)
                else:
                    # Para otros tipos, solo el tipo debe ser único
                    key = (line.payment_method_type, 0)
                
                if key in seen_combinations:
                    if line.payment_method_type == 'extra_financiamiento':
                        raise ValidationError(
                            _('Ya existe una línea de Extra Financiamiento con %s meses en este convenio.') % line.months
                        )
                    else:
                        raise ValidationError(
                            _('No puede haber tipos de método de pago duplicados en el mismo convenio.')
                        )
                seen_combinations.add(key)


class CardAgreementLine(models.Model):
    _name = 'card.agreement.line'
    _description = 'Línea de Convenio de Tarjetas'
    _order = 'sequence, payment_method_type'

    card_agreement_id = fields.Many2one(
        'card.agreement',
        string='Convenio de Tarjetas',
        required=True,
        ondelete='cascade'
    )
    payment_method_type = fields.Selection([
        ('normal', 'Normal'),
        ('extra_financiamiento', 'Extra Financiamiento'),
        ('link_pago', 'Link de Pago'),
        ('puntos', 'Puntos'),
        ('millas', 'Millas'),
    ], string='Tipo de Método de Pago', required=True, help='Tipo de método de pago')
    
    # Campos para periodos de financiamiento
    months = fields.Integer(
        string='Meses',
        default=0,
        help='Número de meses para financiamiento (0 para Normal, Puntos, Link de Pago, Millas; 3, 6, 9, 12 para Extra Financiamiento)'
    )
    
    commission_percentage = fields.Float(
        string='Porcentaje de Comisión (%)',
        required=True,
        digits=(16, 4),
        help='Porcentaje de comisión aplicable (ej: 3.00, 2.40, 3.40, etc.)'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de visualización'
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
        help='Nombre descriptivo de la línea'
    )

    @api.depends('payment_method_type', 'commission_percentage', 'months')
    def _compute_name(self):
        """Generar nombre descriptivo basado en el tipo y porcentaje"""
        for line in self:
            method_names = {
                'normal': 'NORMAL',
                'extra_financiamiento': 'EXTRA FINANCIAMIENTO',
                'link_pago': 'LINK DE PAGO',
                'puntos': 'PUNTOS',
                'millas': 'MILLAS',
            }
            method_name = method_names.get(line.payment_method_type, line.payment_method_type)
            
            if line.payment_method_type == 'extra_financiamiento' and line.months > 0:
                line.name = f"{line.commission_percentage:.2f}% {line.months} MESES"
            elif line.payment_method_type == 'normal':
                line.name = f"{line.commission_percentage:.2f}% NORMAL"
            else:
                line.name = f"{line.commission_percentage:.2f}% {method_name}"

    @api.constrains('commission_percentage')
    def _check_commission_percentage(self):
        """Validar que el porcentaje de comisión sea positivo"""
        for line in self:
            if line.commission_percentage < 0:
                raise ValidationError(_('El porcentaje de comisión debe ser mayor o igual a 0.'))

    @api.constrains('payment_method_type', 'months')
    def _check_months_for_payment_type(self):
        """Validar que los meses solo sean mayores a 0 para Extra Financiamiento"""
        for line in self:
            if line.payment_method_type != 'extra_financiamiento' and line.months != 0:
                raise ValidationError(
                    _('Los meses solo deben ser mayores a 0 para Extra Financiamiento.')
                )
