# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # Toggle Efectivo/Tarjeta/Transferencia - solo para pagos de cliente
    payment_method_toggle = fields.Selection([
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
    ], string='Tipo de Pago',
       help='Seleccione el tipo de pago para ver los diarios disponibles. Sin selección no se muestra ningún diario.')

    payment_notes = fields.Text(string='Notas', help='Notas u observaciones del pago')

    show_payment_toggles = fields.Boolean(
        compute='_compute_show_payment_toggles',
        help='True solo para pagos de cliente (inbound), NO para proveedores',
    )

    @api.depends('partner_type', 'payment_type')
    def _compute_show_payment_toggles(self):
        for w in self:
            w.show_payment_toggles = (
                w.partner_type == 'customer' and w.payment_type == 'inbound'
            )

    @api.model
    def default_get(self, fields_list):
        """Sobrescribir default_get para cargar el convenio automáticamente cuando hay un diario"""
        res = super().default_get(fields_list)
        # payment_method_toggle se establece después cuando se cargan los batches
        # Buscar el diario en los valores por defecto o en el contexto
        journal_id = res.get('journal_id') or self.env.context.get('default_journal_id')
        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
            # Verificar que sea tipo banco y tenga is_credit_card activado
            if journal.type == 'bank' and journal.is_credit_card:
                agreement = self.env['card.agreement'].search([
                    ('journal_id', '=', journal.id),
                    ('company_id', '=', self.env.company.id),
                    ('active', '=', True)
                ], limit=1)
                if agreement:
                    # Agregar card_agreement_id aunque no esté en fields_list para que se cargue
                    res['card_agreement_id'] = agreement.id
        
        return res

    payment_method_type = fields.Selection([
        ('extra_financiamiento', 'Usar Extra Financiamiento'),
        ('link_pago', 'Link de Pago'),
        ('puntos', 'Puntos'),
        ('millas', 'Millas'),
    ], string='Tipo de Método de Pago', help='Seleccione el tipo de método de pago adicional')
    
    # Campo para seleccionar meses directamente del convenio
    months = fields.Selection([
        ('0', '0 Meses (Normal)'),
        ('3', '3 Meses'),
        ('6', '6 Meses'),
        ('9', '9 Meses'),
        ('12', '12 Meses'),
    ], string='Meses', help='Número de meses para financiamiento (solo aplica para Extra Financiamiento)')
    
    # Mantener compatibilidad con código existente
    @api.depends('payment_method_type')
    def _compute_extra_financiar(self):
        for wizard in self:
            wizard.extra_financiar = wizard.payment_method_type == 'extra_financiamiento'
    
    extra_financiar = fields.Boolean(
        'Usar Extra Financiamiento', 
        compute='_compute_extra_financiar',
        store=False,
        help='Si es True, el extra se mostrará en el pago para financiar'
    )

    @api.depends('journal_id', 'journal_id.type', 'journal_id.is_credit_card', 'payment_type', 'partner_type', 'card_agreement_id')
    def _compute_show_extra(self):
        """Mostrar campo extra solo si el diario es tipo banco, está marcado como tarjeta de crédito y tiene convenio"""
        for wizard in self:
            # Primero verificar condiciones básicas
            basic_conditions = (
                wizard.journal_id and
                wizard.journal_id.type == 'bank' and
                wizard.journal_id.is_credit_card and
                wizard.payment_type == 'inbound' and
                wizard.partner_type == 'customer'
            )
            
            if basic_conditions and not wizard.card_agreement_id:
                # Si cumple condiciones básicas pero no tiene convenio, intentar cargarlo
                agreement = self.env['card.agreement'].search([
                    ('journal_id', '=', wizard.journal_id.id),
                    ('company_id', '=', wizard.company_id.id),
                    ('active', '=', True)
                ], limit=1)
                if agreement:
                    wizard.card_agreement_id = agreement
            
            wizard.show_extra = basic_conditions and bool(wizard.card_agreement_id)
    
    @api.depends('payment_method_type', 'card_agreement_id')
    def _compute_show_months(self):
        """Mostrar campo months solo si se selecciona Usar Extra Financiamiento y hay convenio"""
        for wizard in self:
            wizard.show_months = (
                wizard.payment_method_type == 'extra_financiamiento' and
                wizard.card_agreement_id and
                wizard.card_agreement_id.agreement_line_ids.filtered(
                    lambda l: l.payment_method_type == 'extra_financiamiento' and l.active
                )
            )
    
    show_months = fields.Boolean(
        string='Mostrar Meses',
        compute='_compute_show_months',
        store=False
    )
    

    show_extra = fields.Boolean(
        string='Mostrar Extra',
        compute='_compute_show_extra',
        store=False
    )
    
    # Campos invisibles para cálculos
    card_agreement_id = fields.Many2one(
        'card.agreement',
        string='Convenio de Tarjetas',
        domain="[('journal_id', '=', journal_id), ('active', '=', True)]",
        help='Convenio de tarjetas asociado al diario seleccionado'
    )
    
    # Campos computados para la tabla de deducciones
    amount_without_vat = fields.Monetary(
        string='Monto sin IVA',
        compute='_compute_deduction_details',
        currency_field='currency_id',
        readonly=True
    )
    vat_amount = fields.Monetary(
        string='IVA',
        compute='_compute_deduction_details',
        currency_field='currency_id',
        readonly=True
    )
    commission_amount = fields.Monetary(
        string='Comisión',
        compute='_compute_deduction_details',
        currency_field='currency_id',
        readonly=True
    )
    commission_vat_amount = fields.Monetary(
        string='IVA Comisión 13%',
        compute='_compute_deduction_details',
        currency_field='currency_id',
        readonly=True
    )
    retention_amount = fields.Monetary(
        string='Retención',
        compute='_compute_deduction_details',
        currency_field='currency_id',
        readonly=True
    )
    amount_to_receive = fields.Monetary(
        string='Monto a Recibir',
        compute='_compute_deduction_details',
        currency_field='currency_id',
        readonly=True
    )
    total_deductions = fields.Monetary(
        string='Total Deducciones',
        compute='_compute_deduction_details',
        currency_field='currency_id',
        readonly=True
    )
    commission_percentage = fields.Float(
        string='Porcentaje de Comisión (%)',
        compute='_compute_commission_percentage',
        store=False,
        digits=(16, 4),
        readonly=True
    )

    @api.depends('journal_id', 'payment_method_type', 'card_agreement_id', 'months', 'amount', 'currency_id')
    def _compute_commission_percentage(self):
        """Calcular el porcentaje de comisión según el convenio y tipo de método"""
        for wizard in self:
            commission = 0.0
            if wizard.card_agreement_id and wizard.payment_method_type:
                # Buscar la línea del convenio que coincida con el tipo de método
                lines = wizard.card_agreement_id.agreement_line_ids.filtered(
                    lambda l: l.payment_method_type == wizard.payment_method_type and l.active
                )
                if lines:
                    # Convertir months a entero para comparación
                    months_int = int(wizard.months) if wizard.months else 0
                    
                    # Si es extra_financiamiento, buscar por meses
                    if wizard.payment_method_type == 'extra_financiamiento':
                        line = lines.filtered(lambda l: l.months == months_int)
                        if line:
                            commission = line[0].commission_percentage
                        elif lines:
                            # Si no hay coincidencia exacta, tomar la primera disponible
                            commission = lines[0].commission_percentage
                    else:
                        # Para otros tipos de pago, buscar línea con months=0 o la primera disponible
                        line = lines.filtered(lambda l: l.months == 0)
                        if line:
                            commission = line[0].commission_percentage
                        elif lines:
                            commission = lines[0].commission_percentage
            wizard.commission_percentage = commission

    @api.depends('amount', 'commission_percentage', 'card_agreement_id', 'payment_method_type', 'currency_id', 'months')
    def _compute_deduction_details(self):
        """Calcular los detalles de deducciones para mostrar en la tabla informativa"""
        for wizard in self:
            # Valores por defecto
            wizard.amount_without_vat = 0.0
            wizard.vat_amount = 0.0
            wizard.commission_amount = 0.0
            wizard.commission_vat_amount = 0.0
            wizard.retention_amount = 0.0
            wizard.total_deductions = 0.0
            wizard.amount_to_receive = wizard.amount or 0.0
            
            # Si no hay monto, tipo de método es 'none', o no hay convenio, mantener valores en 0
            if not wizard.amount or not wizard.payment_method_type or not wizard.card_agreement_id:
                continue
            
            # Si no hay porcentaje de comisión válido, mantener valores en 0
            if not wizard.commission_percentage or wizard.commission_percentage <= 0:
                continue
            
            # Calcular monto sin IVA (asumiendo IVA del 13%)
            vat_rate = 0.13  # 13% IVA
            amount_without_vat = wizard.amount / (1 + vat_rate)
            vat_amount = wizard.amount - amount_without_vat
            
            # Calcular comisión: Monto sin IVA * % Comisión
            commission_amount = amount_without_vat * (wizard.commission_percentage / 100.0)
            
            # Calcular IVA sobre comisión: Comisión * 13%
            commission_vat_amount = commission_amount * vat_rate
            
            # Calcular retención: Monto sin IVA * 2%
            retention_rate = 0.02  # 2% retención
            retention_amount = amount_without_vat * retention_rate
            
            # Total deducciones
            total_deductions = commission_amount + commission_vat_amount + retention_amount
            
            # Asignar valores calculados
            wizard.amount_without_vat = amount_without_vat
            wizard.vat_amount = vat_amount
            wizard.commission_amount = commission_amount
            wizard.commission_vat_amount = commission_vat_amount
            wizard.retention_amount = retention_amount
            wizard.total_deductions = total_deductions
            wizard.amount_to_receive = wizard.amount - total_deductions

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
                self.payment_method_type = False
        else:
            self.card_agreement_id = False
            self.payment_method_type = False
    
    @api.onchange('payment_method_type', 'months', 'card_agreement_id', 'amount')
    def _onchange_payment_method_type(self):
        """Actualizar cálculos cuando cambia el tipo de método de pago o meses"""
        # Si cambia el tipo de método y es extra_financiamiento, seleccionar el primer mes disponible
        if self.payment_method_type == 'extra_financiamiento' and self.card_agreement_id:
            lines = self.card_agreement_id.agreement_line_ids.filtered(
                lambda l: l.payment_method_type == 'extra_financiamiento' and l.active
            )
            if lines and not self.months:
                # Seleccionar el primer mes disponible (convertir a string para el Selection)
                available_months = sorted(lines.mapped('months'))
                self.months = str(available_months[0]) if available_months else '0'
        elif self.payment_method_type != 'extra_financiamiento':
            self.months = False
        
        # Forzar recálculo de campos computados para que se actualicen inmediatamente en el frontend
        if self.payment_method_type and self.card_agreement_id:
            self._compute_commission_percentage()
            self._compute_deduction_details()

    @api.onchange('payment_method_toggle')
    def _onchange_payment_method_toggle(self):
        """Al cambiar el tipo de pago, limpiar el diario para forzar selección de uno válido."""
        if self.partner_type == 'customer' and self.payment_type == 'inbound':
            self.journal_id = False

    def _filter_journals_by_toggle(self, journals):
        """Filtra diarios según el toggle Efectivo/Tarjeta/Transferencia (solo cliente inbound).
        Si no hay tipo seleccionado, no muestra ningún diario.
        Usa payment_mode si está definido; si no, lógica automática por tipo e is_credit_card."""
        if self.partner_type != 'customer' or self.payment_type != 'inbound':
            return journals
        toggle = self.payment_method_toggle
        if not toggle:
            return self.env['account.journal']

        def _matches(j):
            if j.payment_mode == 'none':
                return False
            if j.payment_mode in ('efectivo', 'tarjeta', 'transferencia'):
                return j.payment_mode == toggle
            # Lógica automática (backward compat)
            if toggle == 'efectivo':
                return j.type == 'cash'
            if toggle == 'tarjeta':
                return j.type == 'bank' and j.is_credit_card
            if toggle == 'transferencia':
                return j.type == 'bank' and not j.is_credit_card
            return False

        return journals.filtered(_matches)

    @api.depends('batches', 'payment_method_toggle')
    def _compute_available_journal_ids(self):
        """Filtra diarios por toggle Efectivo/Tarjeta/Transferencia en pagos de cliente."""
        super()._compute_available_journal_ids()
        for wizard in self:
            if wizard.partner_type == 'customer' and wizard.payment_type == 'inbound':
                filtered = wizard._filter_journals_by_toggle(wizard.available_journal_ids)
                wizard.available_journal_ids = filtered

    def _create_payment_vals_from_wizard(self, batch_result):
        """Heredar el método para agregar campos solo en pagos de cliente"""
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        # Solo heredar campos si es un pago entrante de cliente
        if self.partner_type == 'customer' and self.payment_type == 'inbound':
            payment_vals['payment_method_type'] = self.payment_method_type
            payment_vals['extra_financiar'] = self.extra_financiar
            if self.card_agreement_id:
                payment_vals['card_agreement_id'] = self.card_agreement_id.id
            if self.payment_method_type == 'extra_financiamiento' and self.months:
                payment_vals['months'] = self.months
            # if self.payment_notes:
            #     payment_vals['payment_comment'] = self.payment_notes
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        """Heredar el método para agregar campos solo en pagos de cliente"""
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        # Solo heredar campos si es un pago entrante de cliente
        if self.partner_type == 'customer' and self.payment_type == 'inbound':
            payment_vals['payment_method_type'] = self.payment_method_type
            payment_vals['extra_financiar'] = self.extra_financiar
            if self.card_agreement_id:
                payment_vals['card_agreement_id'] = self.card_agreement_id.id
            if self.payment_method_type == 'extra_financiamiento' and self.months:
                payment_vals['months'] = self.months
            # if self.payment_notes:
            #     payment_vals['payment_comment'] = self.payment_notes
        return payment_vals

