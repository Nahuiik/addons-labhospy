# -*- coding: utf-8 -*-
"""
Extensión de account.payment para gestión de anticipos de clientes.

Este módulo permite registrar pagos como anticipos de cliente, los cuales
se contabilizan en una cuenta de pasivo corriente conciliable y pueden
ser aplicados posteriormente a facturas del mismo cliente.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'advance.cancel.mixin']

    is_advance = fields.Boolean(
        string='Es Abono/Anticipo',
        default=False,
        tracking=True,
        help='Marca este pago como Abono/Anticipo (cliente o proveedor)'
    )
    advance_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Abono/Anticipo',
        domain=[],
        tracking=True,
        help='Cuenta contable para registrar el anticipo (pasivo para clientes, activo para proveedores)'
    )
    advance_available_amount = fields.Monetary(
        string='Saldo disponible del Abono/Anticipo',
        compute='_compute_advance_available_amount',
        store=True,
        currency_field='currency_id',
        help='Monto del anticipo que aún no ha sido aplicado a facturas'
    )
    advance_link_ids = fields.One2many(
        'account.advance.link',
        'payment_id',
        string='Aplicaciones de Abono/Anticipo',
        readonly=True
    )
    sale_order_advance_link_ids = fields.One2many(
        'sale.order.advance.link',
        'payment_id',
        string='Cotizaciones con anticipo asignado',
        readonly=True,
        help='Cotizaciones a las que se ha asociado este anticipo'
    )
    advance_applied_total = fields.Monetary(
        string='Total aplicado',
        compute='_compute_advance_available_amount',
        store=True,
        currency_field='currency_id',
        help='Total del Abono/Anticipo que ya ha sido aplicado a facturas'
    )
    # Resumen de anticipos del cliente (acumulados)
    advance_links_count = fields.Integer(
        string='Cuotas/Aplicaciones',
        compute='_compute_advance_summary',
        help='Número de aplicaciones de este anticipo a facturas'
    )
    partner_advances_count = fields.Integer(
        string='Anticipos acumulados',
        compute='_compute_advance_summary',
        help='Total de anticipos del cliente'
    )
    partner_advances_total = fields.Monetary(
        string='Total anticipos recibidos',
        compute='_compute_advance_summary',
        currency_field='currency_id',
        help='Suma de todos los anticipos del cliente'
    )
    partner_advances_balance = fields.Monetary(
        string='Saldo total del cliente',
        compute='_compute_advance_summary',
        currency_field='currency_id',
        help='Saldo disponible total en anticipos del cliente'
    )
    partner_quotations_with_advances = fields.Char(
        string='Cotizaciones con anticipos',
        compute='_compute_partner_quotations_with_advances',
        help='Números de cotización del cliente que tienen anticipos asignados'
    )
    sale_order_quota_ids = fields.Many2many(
        'sale.order.advance.quota',
        string='Cuotas de la cotización',
        compute='_compute_sale_order_quota_ids',
        help='Plan de cuotas de la cotización destino (visible cuando se registra desde cotización)'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Cotización de origen',
        help='Si se registró desde una cotización, se autoasignará al confirmar.',
        ondelete='set null',
    )
    advance_cancel_allowed = fields.Boolean(
        string='Puede cancelar anticipo',
        compute='_compute_advance_cancel_allowed',
        help='False si pasó el día de creación y el usuario no tiene permiso especial.',
    )

    # Tipo de pago (Efectivo/Tarjeta/Transferencia) - filtra diarios en anticipos de cliente
    payment_method_toggle = fields.Selection([
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
    ], string='Tipo de Pago',
       help='Seleccione el tipo de pago para ver los diarios disponibles. Sin selección no se muestra ningún diario.')

    show_payment_toggles = fields.Boolean(
        compute='_compute_show_payment_toggles',
        help='True solo para anticipos de cliente (inbound)',
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('is_advance', 'create_date')
    def _compute_advance_cancel_allowed(self):
        for payment in self:
            if not payment.is_advance:
                payment.advance_cancel_allowed = True
            else:
                payment.advance_cancel_allowed = (
                    payment._advance_cancel_allowed_for_record(payment)
                )

    @api.depends('is_advance', 'partner_type', 'payment_type')
    def _compute_show_payment_toggles(self):
        for p in self:
            p.show_payment_toggles = (
                p.is_advance and
                p.partner_type == 'customer' and
                p.payment_type == 'inbound'
            )

    @api.depends('company_id', 'is_advance', 'partner_type', 'payment_type', 'payment_method_toggle')
    def _compute_available_journal_ids(self):
        super()._compute_available_journal_ids()
        for payment in self:
            if payment.show_payment_toggles:
                filtered = payment._filter_journals_by_toggle(payment.available_journal_ids)
                payment.available_journal_ids = filtered

    def _filter_journals_by_toggle(self, journals):
        """Filtra diarios según Efectivo/Tarjeta/Transferencia (misma lógica que gn_payment_extra)."""
        if not self.show_payment_toggles:
            return journals
        toggle = self.payment_method_toggle
        if not toggle:
            return self.env['account.journal']

        def _matches(j):
            if hasattr(j, 'payment_mode') and j.payment_mode == 'none':
                return False
            if hasattr(j, 'payment_mode') and j.payment_mode in ('efectivo', 'tarjeta', 'transferencia'):
                return j.payment_mode == toggle
            if toggle == 'efectivo':
                return j.type == 'cash'
            if toggle == 'tarjeta':
                return j.type == 'bank' and getattr(j, 'is_credit_card', False)
            if toggle == 'transferencia':
                return j.type == 'bank' and not getattr(j, 'is_credit_card', False)
            return False

        return journals.filtered(_matches)

    # -------------------------------------------------------------------------

    @api.depends('amount', 'advance_link_ids.amount', 'state', 'is_advance')
    def _compute_advance_available_amount(self):
        """
        Calcula el saldo disponible del anticipo restando las aplicaciones.
        
        El campo es almacenado para permitir búsquedas y filtros eficientes.
        Se recalcula cuando cambia el monto, las aplicaciones o el estado.
        
        Para anticipos en borrador, también se calcula el saldo disponible
        para que aparezcan en los filtros.
        """
        for payment in self:
            if payment.is_advance:
                # Calcular saldo disponible para anticipos en borrador, en proceso o pagados
                # Los estados válidos son: 'draft', 'in_process', 'paid'
                if payment.state in ('draft', 'in_process', 'paid'):
                    applied_amount = sum(payment.advance_link_ids.filtered(lambda l: l.state == 'applied').mapped('amount'))
                    payment.advance_applied_total = applied_amount
                    payment.advance_available_amount = payment.amount - applied_amount
                else:
                    payment.advance_available_amount = 0.0
                    payment.advance_applied_total = 0.0
            else:
                payment.advance_available_amount = 0.0
                payment.advance_applied_total = 0.0

    @api.depends('advance_link_ids', 'advance_link_ids.state', 'partner_id', 'company_id',
                 'partner_type', 'currency_id', 'is_advance')
    def _compute_advance_summary(self):
        """Calcula cuotas, anticipos acumulados y saldo del cliente/proveedor."""
        for payment in self:
            # Cuotas: número de aplicaciones de este anticipo
            applied_links = payment.advance_link_ids.filtered(lambda l: l.state == 'applied')
            payment.advance_links_count = len(applied_links)

            # Anticipos acumulados del partner (solo si es anticipo con partner)
            if not payment.partner_id or not payment.is_advance:
                payment.partner_advances_count = 0
                payment.partner_advances_total = 0.0
                payment.partner_advances_balance = 0.0
                continue

            if payment.partner_type == 'customer' and payment.payment_type == 'inbound':
                advances = payment.partner_id.advance_payment_ids.filtered(
                    lambda p: p.state in ('in_process', 'paid', 'draft')
                    and p.company_id == payment.company_id
                    and (not payment.currency_id or p.currency_id == payment.currency_id)
                )
            elif payment.partner_type == 'supplier' and payment.payment_type == 'outbound':
                advances = payment.partner_id.vendor_advance_payment_ids.filtered(
                    lambda p: p.state in ('in_process', 'paid', 'draft')
                    and p.company_id == payment.company_id
                    and (not payment.currency_id or p.currency_id == payment.currency_id)
                )
            else:
                advances = self.env['account.payment']

            payment.partner_advances_count = len(advances)
            payment.partner_advances_total = sum(advances.mapped('amount'))
            payment.partner_advances_balance = sum(advances.mapped('advance_available_amount'))

    @api.depends('sale_order_id', 'partner_id', 'is_advance', 'partner_type', 'payment_type')
    def _compute_partner_quotations_with_advances(self):
        """Muestra el número de cotización destino o las cotizaciones con anticipos del cliente."""
        for payment in self:
            if not payment.is_advance or payment.partner_type != 'customer' or payment.payment_type != 'inbound':
                payment.partner_quotations_with_advances = ''
                continue
            if payment.sale_order_id:
                payment.partner_quotations_with_advances = payment.sale_order_id.name
            elif payment.partner_id:
                links = self.env['sale.order.advance.link'].search([
                    ('payment_id.partner_id', '=', payment.partner_id.id),
                    ('payment_id.company_id', '=', payment.company_id.id),
                    ('payment_id.is_advance', '=', True),
                    ('payment_id.state', 'in', ('in_process', 'paid')),
                ])
                orders = links.mapped('sale_order_id')
                payment.partner_quotations_with_advances = ', '.join(orders.mapped('name')) if orders else ''
            else:
                payment.partner_quotations_with_advances = ''

    @api.depends('sale_order_id', 'sale_order_id.advance_quota_ids')
    def _compute_sale_order_quota_ids(self):
        """Cuotas de la cotización destino (cuando se registra desde cotización)."""
        for payment in self:
            if payment.sale_order_id:
                payment.sale_order_quota_ids = payment.sale_order_id.advance_quota_ids
            else:
                payment.sale_order_quota_ids = self.env['sale.order.advance.quota']

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------

    @api.constrains('partner_id', 'journal_id', 'payment_type', 'partner_type', 'amount')
    def _check_advance_locked_fields(self):
        """
        Valida que los campos críticos no se puedan modificar cuando el anticipo está en proceso o pagado.
        
        Raises:
            ValidationError: Si se intenta modificar campos bloqueados
        """
        for payment in self:
            if payment.is_advance and payment.state in ('in_process', 'paid'):
                # Verificar si se están intentando cambiar campos bloqueados
                # Esto se hace comparando los valores actuales con los valores en el contexto de escritura
                # Nota: Esta validación se ejecuta antes de write(), por lo que necesitamos otra estrategia
                pass  # La validación real se hace en write()

    def write(self, vals):
        """
        Sobrescribe write para prevenir cambios en campos críticos cuando está en proceso o pagado.
        También establece payment_move_type a "Otro" automáticamente cuando es anticipo.
        """
        # Establecer payment_move_type a "Otro" automáticamente cuando se marca como anticipo
        if 'is_advance' in vals and vals['is_advance']:
            if hasattr(self, 'payment_move_type') and self.payment_type == 'outbound':
                vals['payment_move_type'] = 'otro'
        
        for payment in self:
            if payment.is_advance and payment.state in ('in_process', 'paid'):
                # Campos que no se pueden modificar cuando está en proceso o pagado
                locked_fields = ['partner_id', 'journal_id', 'payment_type', 'partner_type', 'amount', 
                                'advance_account_id', 'is_advance', 'date', 'currency_id']
                for field in locked_fields:
                    if field in vals:
                        raise ValidationError(_(
                            'No se puede modificar el campo "%s" cuando el anticipo está en estado "%s".',
                            self.env['ir.model.fields']._get('account.payment', field).name if hasattr(self.env['ir.model.fields'], '_get') else field,
                            dict(self._fields['state'].selection)[payment.state]
                        ))
        return super().write(vals)
    
    @api.model_create_multi
    def create(self, vals_list):
        """
        Establece payment_move_type a "Otro" automáticamente cuando se crea un anticipo.
        """
        for vals in vals_list:
            if vals.get('is_advance') and vals.get('payment_type') == 'outbound':
                if hasattr(self.env['account.payment'], 'payment_move_type'):
                    vals['payment_move_type'] = 'otro'
        return super().create(vals_list)

    @api.constrains('is_advance', 'advance_account_id', 'partner_id', 'partner_type', 'company_id')
    def _check_advance_requirements(self):
        """
        Valida que los anticipos cumplan con los requisitos mínimos:
        - Cuenta de anticipo obligatoria y conciliable
        - Partner (cliente) obligatorio
        - Solo para pagos de tipo cliente (inbound)
        - Cuenta debe pertenecer a la misma compañía
        
        Raises:
            ValidationError: Si no se cumplen los requisitos
        """
        for payment in self:
            if payment.is_advance:
                if not payment.advance_account_id:
                    raise ValidationError(_(
                        'La cuenta de anticipo es obligatoria cuando el pago está marcado como anticipo.'
                    ))
                if not payment.advance_account_id.reconcile:
                    raise ValidationError(_(
                        'La cuenta de anticipo "%s" debe ser conciliable.',
                        payment.advance_account_id.name
                    ))
                # Validar que la cuenta pertenezca a la misma compañía
                if payment.company_id and payment.advance_account_id.company_ids:
                    if payment.company_id not in payment.advance_account_id.company_ids:
                        raise ValidationError(_(
                            'La cuenta de anticipo "%s" no pertenece a la compañía "%s".',
                            payment.advance_account_id.name, payment.company_id.name
                        ))
                if not payment.partner_id:
                    raise ValidationError(_(
                        'El partner es obligatorio para anticipos.'
                    ))
                # Los anticipos solo aplican a clientes o proveedores.
                # No se restringe el tipo/grupo contable de la cuenta: basta con que
                # sea conciliable. Así se pueden usar las cuentas de anticipo reales
                # del plan contable sin forzar su clasificación.
                if payment.partner_type not in ('customer', 'supplier'):
                    raise ValidationError(_(
                        'Los anticipos solo están disponibles para clientes o proveedores.'
                    ))

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('payment_method_toggle')
    def _onchange_payment_method_toggle(self):
        """Al cambiar el tipo de pago, limpiar el diario para forzar selección de uno válido."""
        if self.show_payment_toggles:
            self.journal_id = False

    @api.onchange('is_advance', 'company_id', 'partner_type', 'payment_type')
    def _onchange_is_advance(self):
        """
        Cuando se marca como anticipo, carga la cuenta por defecto desde configuración
        y establece el dominio correcto para la cuenta de anticipo según el tipo de partner.
        También establece payment_move_type a "Otro" automáticamente cuando es anticipo.
        Esto mejora la UX al preseleccionar la cuenta más común.
        """
        domain = {}
        if self.is_advance:
            # Establecer payment_move_type a "Otro" automáticamente cuando es anticipo
            if hasattr(self, 'payment_move_type') and self.payment_type == 'outbound':
                self.payment_move_type = 'otro'
            
            # Dominio dinámico: solo cuentas activas y conciliables.
            # No se filtra por grupo contable (activo/pasivo) para permitir
            # seleccionar las cuentas de anticipo reales del plan contable.
            base_domain = [
                ('active', '=', True),
                ('reconcile', '=', True),
            ]
            
            if self.company_id:
                base_domain.append(('company_ids', 'in', [self.company_id.id]))
            domain = {'advance_account_id': base_domain}
            
            # Cargar cuenta por defecto según partner_type
            default_account = self._get_default_advance_account()
            if default_account:
                self.advance_account_id = default_account
        
        return {'domain': domain} if domain else {}

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def _prepare_payment_moves(self):
        """
        Sobrescribe para modificar las líneas del asiento antes de crearlo.
        
        Para anticipos:
        - Clientes: reemplaza la cuenta por cobrar del partner por la cuenta de anticipo (pasivo corriente)
        - Proveedores: reemplaza la cuenta por pagar del partner por la cuenta de anticipo (activo corriente)
        
        Returns:
            list: Lista de diccionarios con los valores de los asientos
        """
        moves = super()._prepare_payment_moves()

        for payment, move_vals in zip(self, moves):
            if payment.is_advance and payment.advance_account_id and move_vals.get('line_ids'):
                for line_command in move_vals['line_ids']:
                    if len(line_command) > 2:
                        line_vals = line_command[2]
                        # Para clientes: reemplazar cuenta de crédito (cuenta por cobrar)
                        # Para proveedores: reemplazar cuenta de débito (cuenta por pagar)
                        if payment.partner_type == 'customer':
                            if (line_vals.get('partner_id') == payment.partner_id.id and
                                    line_vals.get('credit', 0) > 0):
                                line_vals['account_id'] = payment.advance_account_id.id
                        elif payment.partner_type == 'supplier':
                            # Para proveedores: buscar línea de débito con partner
                            # Si no tiene partner_id, asignarlo
                            if line_vals.get('debit', 0) > 0:
                                if line_vals.get('partner_id') == payment.partner_id.id:
                                    line_vals['account_id'] = payment.advance_account_id.id
                                elif not line_vals.get('partner_id'):
                                    # Si la línea no tiene partner pero es débito, puede ser la línea del partner
                                    # Asignar partner y cuenta de anticipo
                                    line_vals['partner_id'] = payment.partner_id.id
                                    line_vals['account_id'] = payment.advance_account_id.id
        return moves

    def action_post(self):
        """
        Sobrescribe para validar anticipos después de postear y generar nombre con secuencia.
        
        Asegura que las líneas del asiento usen la cuenta de anticipo correcta,
        genera el nombre usando la secuencia configurada y registra el evento en el chatter.
        
        Returns:
            bool: Resultado de super().action_post()
            
        Raises:
            ValidationError: Si el asiento no tiene línea con cuenta de anticipo
        """
        # Generar nombre con secuencia antes de postear
        for payment in self:
            if payment.is_advance and not payment.name:
                advance_name = payment._generate_advance_name()
                if advance_name:
                    # Usar write directo para evitar problemas con campos computed
                    payment.with_context(skip_compute_name=True).write({'name': advance_name})
        
        # Modificar las líneas si el asiento ya existe
        for payment in self:
            if payment.is_advance and payment.advance_account_id and payment.move_id and payment.move_id.state == 'draft':
                partner_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.partner_id == payment.partner_id
                )
                if payment.partner_type == 'customer':
                    # Para clientes: línea de crédito (cuenta por cobrar)
                    lines_to_update = partner_lines.filtered(lambda l: l.credit > 0)
                elif payment.partner_type == 'supplier':
                    # Para proveedores: línea de débito (cuenta por pagar)
                    # En pagos salientes a proveedores, la línea de débito es la que usa la cuenta de anticipo
                    lines_to_update = partner_lines.filtered(lambda l: l.debit > 0)
                else:
                    lines_to_update = self.env['account.move.line']
                
                for line in lines_to_update:
                    line.account_id = payment.advance_account_id
                    # Asegurar que el partner esté en la línea
                    if not line.partner_id:
                        line.partner_id = payment.partner_id
        
        res = super().action_post()
        
        # Validar y registrar después de postear
        for payment in self:
            if payment.is_advance:
                move = payment.move_id
                partner = payment.partner_id

                # Asegurar que la línea del partner use la cuenta de anticipo
                partner_lines = move.line_ids.filtered(lambda l: l.partner_id == partner)
                
                if payment.partner_type == 'customer':
                    # Para clientes: validar líneas de crédito
                    lines_to_check = partner_lines.filtered(lambda l: l.credit > 0)
                    for line in lines_to_check:
                        if line.account_id != payment.advance_account_id:
                            line.account_id = payment.advance_account_id
                    move_lines = lines_to_check.filtered(lambda l: l.account_id == payment.advance_account_id)
                    partner_type_label = 'cliente'
                elif payment.partner_type == 'supplier':
                    # Para proveedores: validar líneas de débito (pago saliente = débito en cuenta de anticipo)
                    lines_to_check = partner_lines.filtered(lambda l: l.debit > 0)
                    for line in lines_to_check:
                        if line.account_id != payment.advance_account_id:
                            line.account_id = payment.advance_account_id
                    # También verificar si hay líneas con la cuenta correcta pero sin partner (línea del diario)
                    # En pagos de proveedor, la línea de débito con la cuenta de anticipo debe tener el partner
                    move_lines = partner_lines.filtered(
                        lambda l: l.account_id == payment.advance_account_id and 
                                 l.partner_id == partner and 
                                 l.debit > 0
                    )
                    partner_type_label = 'proveedor'
                else:
                    move_lines = self.env['account.move.line']
                    partner_type_label = 'partner'
                        
                # Validar que exista al menos una línea con la cuenta de anticipo
                if not move_lines:
                    raise ValidationError(_(
                        'El asiento del anticipo no contiene una línea con la cuenta de anticipo y el partner correctos.'
                    ))
                    
                # Registrar en chatter
                payment.message_post(
                    body=_('Anticipo de %s registrado: %s %s', 
                           partner_type_label, payment.amount, payment.currency_id.symbol)
                )

                # Autoasignar a cotización si se registró desde una
                if payment.sale_order_id and payment.partner_type == 'customer':
                    order = payment.sale_order_id
                    if order.partner_id == payment.partner_id:
                        amount = min(
                            payment.amount,
                            payment.advance_available_amount or payment.amount,
                        )
                        if amount > 0:
                            self.env['sale.order.advance.link'].create({
                                'sale_order_id': order.id,
                                'payment_id': payment.id,
                                'amount': amount,
                            })
                            total_linked = sum(
                                link.amount for link in order.advance_link_ids
                                if link.currency_id == order.currency_id
                            )
                            if order.advance_quota_ids and total_linked > 0:
                                order._distribute_advances_to_quotas(total_linked)
                            order.message_post(
                                body=_(
                                    'Anticipo %s autoasignado a esta cotización: %s %s',
                                    payment.name or payment.id,
                                    amount,
                                    payment.currency_id.symbol,
                                ),
                                message_type='notification',
                            )
                    payment.sale_order_id = False  # Evitar duplicados
        return res

    def action_create_quotas_from_advance(self):
        """Abre el wizard para crear cuotas en la cotización destino y heredarlas."""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('Este anticipo no está vinculado a una cotización.'))
        return {
            'name': _('Generar Plan de Cuotas'),
            'type': 'ir.actions.act_window',
            'res_model': 'generate.quotas.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.sale_order_id.id,
            },
        }

    def action_send(self):
        """
        Cambia el estado del anticipo a "En proceso" (in_process).
        
        Para anticipos, este método permite cambiar directamente de "Borrador" 
        a "En proceso" publicando primero el asiento si es necesario.
        
        Returns:
            bool: True si se cambió el estado correctamente
        """
        for payment in self:
            if payment.is_advance and payment.state == 'draft':
                # Primero asegurar que el asiento esté creado y publicado
                if not payment.move_id:
                    # Crear el asiento si no existe
                    payment.action_post()
                elif payment.move_id.state == 'draft':
                    # Publicar el asiento si está en borrador
                    payment.move_id.action_post()
                
                # Cambiar el estado del pago a "in_process" (En proceso)
                payment.write({'state': 'in_process'})
                
                # Registrar en chatter
                payment.message_post(
                    body=_('Anticipo marcado como "En proceso"')
                )
            elif payment.state == 'draft':
                # Para pagos normales, usar el método estándar si existe
                if hasattr(super(AccountPayment, self), 'action_send'):
                    return super(AccountPayment, self).action_send()
                else:
                    # Si no existe, publicar normalmente
                    return payment.action_post()
        
        return True

    def _advance_check_payment_cancel(self, operation_label):
        advances = self.filtered('is_advance')
        if advances:
            self._advance_check_cancel_allowed(advances, operation_label)

    def action_cancel(self):
        self._advance_check_payment_cancel(_('cancelar'))
        return super().action_cancel()

    def action_draft(self):
        self._advance_check_payment_cancel(_('restablecer a borrador'))
        return super().action_draft()

    def action_unpost(self):
        """
        Sobrescribe para validar que no se pueda despublicar si tiene aplicaciones.

        Esto previene inconsistencias contables al proteger anticipos ya utilizados.

        Returns:
            bool: Resultado de super().action_unpost()

        Raises:
            UserError: Si el anticipo tiene aplicaciones
        """
        self._advance_check_payment_cancel(_('despublicar'))
        for payment in self:
            if payment.is_advance and payment.advance_link_ids:
                raise UserError(_(
                    'No se puede despublicar un anticipo que ya tiene aplicaciones. '
                    'Debe revertir primero las aplicaciones.'
                ))
        return super().action_unpost()

    def action_open_apply_to_invoices_wizard(self):
        """
        Abre un wizard para buscar y aplicar este anticipo a facturas pendientes.
        
        Returns:
            dict: Acción para abrir el wizard de aplicación
            
        Raises:
            UserError: Si el anticipo no tiene saldo disponible
        """
        self.ensure_one()
        
        if not self.is_advance:
            raise UserError(_('Este pago no está marcado como anticipo.'))
        
        if self.state not in ('in_process', 'paid'):
            raise UserError(_('El anticipo debe estar en proceso o pagado para poder aplicarlo.'))
        
        if self.advance_available_amount <= 0:
            raise UserError(_('Este anticipo no tiene saldo disponible para aplicar.'))
        
        # Determinar el tipo de factura según el tipo de partner
        if self.partner_type == 'customer':
            move_type = 'out_invoice'
            partner_label = 'cliente'
        elif self.partner_type == 'supplier':
            move_type = 'in_invoice'
            partner_label = 'proveedor'
        else:
            raise UserError(_('Los anticipos solo están disponibles para clientes o proveedores.'))
        
        # Buscar facturas pendientes del partner
        invoices = self.env['account.move'].search([
            ('partner_id', '=', self.partner_id.id),
            ('company_id', '=', self.company_id.id),
            ('move_type', '=', move_type),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
            ('currency_id', '=', self.currency_id.id),
        ], order='invoice_date asc')
        
        if not invoices:
            raise UserError(_('No hay facturas pendientes de pago para este %s.') % partner_label)
        
        # Crear wizard
        wizard = self.env['apply.advance.to.invoices.wizard'].create({
            'payment_id': self.id,
        })
        
        # Crear líneas para cada factura
        for invoice in invoices:
            max_amount = min(self.advance_available_amount, invoice.amount_residual)
            self.env['apply.advance.to.invoices.wizard.line'].create({
                'wizard_id': wizard.id,
                'move_id': invoice.id,
                'amount_to_apply': 0.0,  # El usuario decide cuánto aplicar
                'max_amount': max_amount,
            })
        
        return {
            'name': _('Aplicar Anticipo a Facturas'),
            'type': 'ir.actions.act_window',
            'res_model': 'apply.advance.to.invoices.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    @api.model
    def _get_default_advance_account(self):
        """
        Obtiene la cuenta de anticipo por defecto desde configuración según el tipo de partner.
        
        Returns:
            account.account: Cuenta de anticipo o False si no está configurada
        """
        if self.partner_type == 'customer':
            param_name = 'gts_customer_advance.advance_account_id'
        elif self.partner_type == 'supplier':
            param_name = 'gts_customer_advance.vendor_advance_account_id'
        else:
            return False
        
        param = self.env['ir.config_parameter'].sudo().get_param(param_name)
        if param:
            try:
                account_id = int(param)
                account = self.env['account.account'].browse(account_id)
                if account.exists() and self.env.company in account.company_ids:
                    return account
            except (ValueError, TypeError, AttributeError):
                pass
        return False

    def _get_advance_sequence(self):
        """
        Obtiene la secuencia de anticipo según el tipo de partner.
        
        Returns:
            ir.sequence: Secuencia de anticipo o False si no está configurada
        """
        if self.partner_type == 'customer':
            param_name = 'gts_customer_advance.customer_advance_sequence_id'
            sequence_code = 'customer.advance'
        elif self.partner_type == 'supplier':
            param_name = 'gts_customer_advance.vendor_advance_sequence_id'
            sequence_code = 'vendor.advance'
        else:
            return False
        
        # Primero intentar obtener desde config_parameter
        param = self.env['ir.config_parameter'].sudo().get_param(param_name)
        if param:
            try:
                sequence_id = int(param)
                sequence = self.env['ir.sequence'].browse(sequence_id)
                if sequence.exists():
                    return sequence
            except (ValueError, TypeError, AttributeError):
                pass
        
        # Si no está configurada, buscar por código
        sequence = self.env['ir.sequence'].search([
            ('code', '=', sequence_code),
            ('company_id', 'in', [False, self.company_id.id])
        ], limit=1)
        
        return sequence if sequence.exists() else False

    def _generate_advance_name(self):
        """
        Genera el nombre del anticipo usando la secuencia correspondiente según el tipo de partner.
        
        Returns:
            str: Nombre generado o False si no se puede generar
        """
        if not self.is_advance:
            return False
        
        sequence = self._get_advance_sequence()
        if not sequence:
            _logger.warning(
                'No se encontró secuencia configurada para anticipos de %s. '
                'Configure la secuencia en Ajustes > Contabilidad > Anticipos.',
                self.partner_type
            )
            return False
        
        try:
            # Generar número usando la secuencia
            advance_name = sequence.next_by_id()
            return advance_name
        except Exception as e:
            _logger.error(
                'Error al generar nombre de anticipo para %s: %s',
                self.partner_type, str(e)
            )
            return False

    @api.model
    def _get_available_advances_for_partner(self, partner_id, company_id, currency_id=None, partner_type='customer'):
        """
        Obtiene anticipos disponibles de un partner.
        
        Método helper optimizado que usa el campo almacenado advance_available_amount
        para filtrar en SQL en lugar de Python.
        
        Args:
            partner_id (int): ID del partner
            company_id (int): ID de la compañía
            currency_id (int, optional): ID de la moneda. Si no se especifica, busca en todas las monedas
            partner_type (str): Tipo de partner ('customer' o 'supplier')
            company_id (int): ID de la compañía
            currency_id (int, optional): ID de la moneda para filtrar
            
        Returns:
            account.payment: Recordset de anticipos disponibles
        """
        domain = [
            ('is_advance', '=', True),
            ('partner_type', '=', partner_type),
            ('state', 'in', ['in_process', 'paid']),  # Estados válidos: 'in_process' (En proceso) y 'paid' (Pagado)
            ('partner_id', '=', partner_id),
            ('company_id', '=', company_id),
            ('advance_available_amount', '>', 0),  # Filtro en SQL gracias a store=True
        ]
        
        # Si se especifica currency_id, filtrar también por moneda
        if currency_id:
            domain.append(('currency_id', '=', currency_id))
        
        return self.search(domain, order='date asc')

    @api.model
    def _get_advance_config(self, param_name, default=None):
        """
        Obtiene un parámetro de configuración del módulo de anticipos.
        
        Método centralizado para obtener configuración, evitando código duplicado.
        
        Args:
            param_name (str): Nombre del parámetro (sin prefijo)
            default: Valor por defecto si no existe
            
        Returns:
            str: Valor del parámetro o default
        """
        full_param = f'gts_customer_advance.{param_name}'
        return self.env['ir.config_parameter'].sudo().get_param(full_param, default)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """
        Establece el dominio base para advance_account_id.

        Solo se exige que la cuenta esté activa y sea conciliable; el dominio
        fino por tipo de partner se ajusta en el onchange.

        Returns:
            dict: Diccionario de campos con sus atributos
        """
        res = super().fields_get(allfields=allfields, attributes=attributes)
        
        if 'advance_account_id' in res:
            res['advance_account_id']['domain'] = [
                ('active', '=', True),
                ('reconcile', '=', True),
            ]
        
        return res
