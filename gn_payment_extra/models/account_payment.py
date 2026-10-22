# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

SUPPLIER_PAYMENT_MODIFY_GROUP = 'gn_payment_extra.group_supplier_payment_modify'


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_supplier_invoice_payment = fields.Boolean(
        string='Es pago a factura de proveedor',
        compute='_compute_supplier_payment_flags',
    )
    supplier_payment_locked = fields.Boolean(
        string='Pago proveedor bloqueado',
        compute='_compute_supplier_payment_flags',
        help='True si el pago a proveedor está registrado y el usuario no puede modificarlo.',
    )

    def _is_supplier_invoice_payment(self):
        self.ensure_one()
        if self.partner_type != 'supplier' or self.payment_type != 'outbound':
            return False
        if getattr(self, 'is_advance', False):
            return False
        return True

    def _is_registered_supplier_payment(self):
        self.ensure_one()
        return self._is_supplier_invoice_payment() and self.state not in ('draft', 'canceled')

    def _user_can_modify_supplier_payment(self):
        # Permite flujos internos (p.ej. retención al crear el pago) sin el grupo de modificación.
        if self.env.context.get('skip_payment_write_lock'):
            return True
        return self.env.user.has_group(SUPPLIER_PAYMENT_MODIFY_GROUP)

    @api.depends('partner_type', 'payment_type', 'state')
    def _compute_supplier_payment_flags(self):
        can_modify = self._user_can_modify_supplier_payment()
        for payment in self:
            is_supplier = payment._is_supplier_invoice_payment()
            payment.is_supplier_invoice_payment = is_supplier
            payment.supplier_payment_locked = (
                is_supplier
                and payment.state not in ('draft', 'canceled')
                and not can_modify
            )

    def _check_supplier_payment_modify_permission(self, operation_label):
        blocked = self.filtered(
            lambda p: p._is_registered_supplier_payment()
            and not p._user_can_modify_supplier_payment()
        )
        if not blocked:
            return
        names = ', '.join(blocked[:3].mapped('display_name'))
        if len(blocked) > 3:
            names = _('%s y %s más') % (names, len(blocked) - 3)
        raise UserError(_(
            'No puede %(operation)s el pago «%(names)s». '
            'Se requiere el permiso «Modificar pagos a proveedores».',
            operation=operation_label,
            names=names,
        ))

    def unlink(self):
        locked = self.filtered(
            lambda p: p._is_registered_supplier_payment()
            and not p._user_can_modify_supplier_payment()
        )
        if locked:
            locked._check_supplier_payment_modify_permission(_('eliminar'))
        return super().unlink()

    def action_cancel(self):
        self._check_supplier_payment_modify_permission(_('cancelar'))
        return super().action_cancel()

    def action_draft(self):
        self._check_supplier_payment_modify_permission(_('restablecer a borrador'))
        return super().action_draft()

    def button_request_cancel(self):
        self._check_supplier_payment_modify_permission(_('solicitar cancelación de'))
        return super().button_request_cancel()

    payment_method_type = fields.Selection([
        ('extra_financiamiento', 'Usar Extra Financiamiento'),
        ('link_pago', 'Link de Pago'),
        ('puntos', 'Puntos'),
        ('millas', 'Millas'),
    ], string='Tipo de Método de Pago', help='Seleccione el tipo de método de pago adicional')
    
    # Campo para meses directamente del convenio
    months = fields.Selection([
        ('0', '0 Meses (Normal)'),
        ('3', '3 Meses'),
        ('6', '6 Meses'),
        ('9', '9 Meses'),
        ('12', '12 Meses'),
    ], string='Meses', default='0', help='Número de meses para financiamiento (solo aplica para Extra Financiamiento)')
    
    # Mantener compatibilidad con código existente
    @api.depends('payment_method_type')
    def _compute_extra_financiar(self):
        for payment in self:
            payment.extra_financiar = payment.payment_method_type == 'extra_financiamiento'
    
    extra_financiar = fields.Boolean(
        'Usar Extra Financiamiento', 
        compute='_compute_extra_financiar',
        store=True,
        help='Si es True, el extra se mostrará en el pago para financiar'
    )

    @api.depends('journal_id', 'journal_id.type', 'journal_id.is_credit_card', 'payment_type', 'partner_type', 'card_agreement_id')
    def _compute_show_extra(self):
        """Mostrar campo extra solo si el diario es tipo banco, está marcado como tarjeta de crédito y tiene convenio"""
        for payment in self:
            # Primero verificar condiciones básicas
            basic_conditions = (
                payment.journal_id and
                payment.journal_id.type == 'bank' and
                payment.journal_id.is_credit_card and
                payment.payment_type == 'inbound' and
                payment.partner_type == 'customer'
            )
            
            if basic_conditions and not payment.card_agreement_id:
                # Si cumple condiciones básicas pero no tiene convenio, intentar cargarlo
                agreement = self.env['card.agreement'].search([
                    ('journal_id', '=', payment.journal_id.id),
                    ('company_id', '=', payment.company_id.id),
                    ('active', '=', True)
                ], limit=1)
                if agreement:
                    payment.card_agreement_id = agreement
            
            payment.show_extra = basic_conditions and bool(payment.card_agreement_id)

    show_extra = fields.Boolean(
        string='Mostrar Extra',
        compute='_compute_show_extra',
        store=True
    )
    
    card_agreement_id = fields.Many2one(
        'card.agreement',
        string='Convenio de Tarjetas',
        domain="[('journal_id', '=', journal_id), ('active', '=', True)]",
        help='Convenio de tarjetas asociado al diario seleccionado'
    )
    
    commission_percentage = fields.Float(
        string='Porcentaje de Comisión (%)',
        compute='_compute_commission_percentage',
        store=False,
        digits=(16, 4),
        help='Porcentaje de comisión según el tipo de método de pago seleccionado'
    )
    
    # Campos computados para la tabla de deducciones (almacenados para que el reporte pueda leerlos)
    amount_without_vat = fields.Monetary(
        string='Monto sin IVA',
        compute='_compute_deduction_details',
        store=True,
        currency_field='currency_id',
        readonly=True
    )
    vat_amount = fields.Monetary(
        string='IVA',
        compute='_compute_deduction_details',
        store=True,
        currency_field='currency_id',
        readonly=True
    )
    commission_amount = fields.Monetary(
        string='Comisión',
        compute='_compute_deduction_details',
        store=True,
        currency_field='currency_id',
        readonly=True
    )
    commission_vat_amount = fields.Monetary(
        string='IVA Comisión 13%',
        compute='_compute_deduction_details',
        store=True,
        currency_field='currency_id',
        readonly=True
    )
    retention_amount = fields.Monetary(
        string='Retención',
        compute='_compute_deduction_details',
        store=True,
        currency_field='currency_id',
        readonly=True
    )
    amount_to_receive = fields.Monetary(
        string='Monto a Recibir',
        compute='_compute_deduction_details',
        store=True,
        currency_field='currency_id',
        readonly=True
    )
    total_deductions = fields.Monetary(
        string='Total Deducciones',
        compute='_compute_deduction_details',
        store=True,
        currency_field='currency_id',
        readonly=True
    )

    def _get_months_int(self):
        """Convertir el campo months (Selection string) a entero de forma segura"""
        if not self.months:
            return 0
        try:
            return int(self.months)
        except (ValueError, TypeError):
            return 0

    @api.depends('journal_id', 'payment_method_type', 'card_agreement_id', 'months')
    def _compute_commission_percentage(self):
        """Calcular el porcentaje de comisión según el convenio y tipo de método"""
        for payment in self:
            commission = 0.0
            if payment.card_agreement_id and payment.payment_method_type:
                # Convertir months a entero antes del filtered para evitar closure issues
                months_int = payment._get_months_int()
                
                # Buscar la línea del convenio que coincida con el tipo de método
                lines = payment.card_agreement_id.agreement_line_ids.filtered(
                    lambda l: l.payment_method_type == payment.payment_method_type and l.active
                )
                if lines:
                    # Si es extra_financiamiento, buscar por meses
                    if payment.payment_method_type == 'extra_financiamiento':
                        # Buscar línea que coincida con los meses
                        matching_line = False
                        for line in lines:
                            if line.months == months_int:
                                matching_line = line
                                break
                        if matching_line:
                            commission = matching_line.commission_percentage
                        elif lines:
                            # Si no hay coincidencia exacta, tomar la primera disponible
                            commission = lines[0].commission_percentage
                    else:
                        # Para otros tipos de pago, buscar línea con months=0 o la primera disponible
                        matching_line = False
                        for line in lines:
                            if line.months == 0:
                                matching_line = line
                                break
                        if matching_line:
                            commission = matching_line.commission_percentage
                        elif lines:
                            commission = lines[0].commission_percentage
            payment.commission_percentage = commission

    @api.depends('amount', 'commission_percentage', 'card_agreement_id', 'payment_method_type', 'currency_id', 'months', 'state')
    def _compute_deduction_details(self):
        """Calcular los detalles de deducciones para mostrar en la tabla informativa"""
        for payment in self:
            # Valores por defecto
            payment.amount_without_vat = 0.0
            payment.vat_amount = 0.0
            payment.commission_amount = 0.0
            payment.commission_vat_amount = 0.0
            payment.retention_amount = 0.0
            payment.total_deductions = 0.0
            payment.amount_to_receive = payment.amount or 0.0
            
            # Si no hay monto, tipo de método es 'none', o no hay porcentaje de comisión, mantener valores en 0
            if not payment.amount or not payment.payment_method_type:
                continue
            
            if not payment.commission_percentage or payment.commission_percentage <= 0:
                continue
            
            # Calcular monto sin IVA (asumiendo IVA del 13%)
            vat_rate = 0.13  # 13% IVA
            amount_without_vat = payment.amount / (1 + vat_rate)
            vat_amount = payment.amount - amount_without_vat
            
            # Calcular comisión: Monto sin IVA * % Comisión
            commission_amount = amount_without_vat * (payment.commission_percentage / 100.0)
            
            # Calcular IVA sobre comisión: Comisión * 13%
            commission_vat_amount = commission_amount * vat_rate
            
            # Calcular retención: Monto sin IVA * 2%
            retention_rate = 0.02  # 2% retención
            retention_amount = amount_without_vat * retention_rate
            
            # Total deducciones
            total_deductions = commission_amount + commission_vat_amount + retention_amount
            
            # Asignar valores calculados
            payment.amount_without_vat = amount_without_vat
            payment.vat_amount = vat_amount
            payment.commission_amount = commission_amount
            payment.commission_vat_amount = commission_vat_amount
            payment.retention_amount = retention_amount
            payment.total_deductions = total_deductions
            payment.amount_to_receive = payment.amount - total_deductions

    def action_post(self):
        """Recalcular comisiones antes de publicar (con lock de sucursal desactivado)."""
        payments = self.with_context(skip_payment_write_lock=True)
        payments._compute_commission_percentage()
        payments._compute_deduction_details()
        return super(AccountPayment, payments).action_post()

    @api.onchange('journal_id')
    def _onchange_journal_id_card_agreement(self):
        """Cargar el convenio de tarjetas cuando se selecciona un diario"""
        if self.journal_id and self.journal_id.type == 'bank' and self.journal_id.is_credit_card:
            agreement = self.env['card.agreement'].search([
                ('journal_id', '=', self.journal_id.id),
                ('company_id', '=', self.company_id.id),
                ('active', '=', True)
            ], limit=1)
            if agreement:
                self.card_agreement_id = agreement
            else:
                self.card_agreement_id = False
        else:
            self.card_agreement_id = False

    @api.onchange('payment_method_type', 'months', 'card_agreement_id', 'amount')
    def _onchange_payment_method_type(self):
        """Actualizar cálculos cuando cambia el tipo de método de pago o meses"""
        # Si cambia el tipo de método y es extra_financiamiento, seleccionar el primer mes disponible
        if self.payment_method_type == 'extra_financiamiento' and self.card_agreement_id:
            lines = self.card_agreement_id.agreement_line_ids.filtered(
                lambda l: l.payment_method_type == 'extra_financiamiento' and l.active
            )
            if lines and not self.months:
                # Seleccionar el primer mes disponible (como string para el Selection)
                available_months = [line.months for line in lines]
                available_months.sort()
                self.months = str(available_months[0]) if available_months else '0'
        elif self.payment_method_type != 'extra_financiamiento':
            self.months = '0'
        
        # Forzar recálculo de campos computados para que se actualicen inmediatamente en el frontend
        if self.payment_method_type and self.card_agreement_id:
            self._compute_commission_percentage()
            self._compute_deduction_details()

