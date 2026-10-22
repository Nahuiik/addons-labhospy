# -*- coding: utf-8 -*-
"""
Wizards para aplicar anticipos de clientes.

Este módulo contiene los wizards para:
1. Aplicar anticipos a una factura específica (desde la factura)
2. Aplicar un anticipo a múltiples facturas (desde el pago)
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


# =============================================================================
# WIZARD: Aplicar anticipos a una factura (desde la factura)
# =============================================================================

class ApplyAdvanceWizardLine(models.TransientModel):
    """Líneas del wizard para seleccionar anticipos a aplicar"""
    _name = 'apply.advance.wizard.line'
    _description = 'Línea de Wizard de Aplicación de Abono/Anticipo'

    wizard_id = fields.Many2one(
        'apply.advance.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Abono/Anticipo',
        required=True,
        readonly=True
    )
    payment_date = fields.Date(
        string='Fecha',
        related='payment_id.date',
        readonly=True
    )
    payment_name = fields.Char(
        string='Referencia',
        related='payment_id.name',
        readonly=True
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        related='payment_id.journal_id',
        readonly=True
    )
    available_amount = fields.Monetary(
        string='Saldo Disponible',
        currency_field='currency_id',
        readonly=True,
        help='Saldo disponible del Abono/Anticipo'
    )
    amount_to_apply = fields.Monetary(
        string='Monto a Aplicar',
        currency_field='currency_id',
        required=True,
        help='Monto del Abono/Anticipo a aplicar a esta factura'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='payment_id.currency_id',
        readonly=True
    )
    selected = fields.Boolean(
        string='Seleccionado',
        compute='_compute_selected',
        store=True
    )

    @api.depends('amount_to_apply')
    def _compute_selected(self):
        """Determina si la línea está seleccionada (monto > 0)."""
        for line in self:
            line.selected = line.amount_to_apply > 0

    @api.constrains('amount_to_apply', 'available_amount')
    def _check_amount_to_apply(self):
        """Valida que el monto a aplicar no exceda el saldo disponible."""
        for line in self:
            if line.amount_to_apply > line.available_amount:
                raise ValidationError(_(
                    'El monto a aplicar (%s) no puede ser mayor que el saldo disponible (%s) del Abono/Anticipo %s.',
                    line.amount_to_apply, line.available_amount, line.payment_id.name
                ))
            if line.amount_to_apply < 0:
                raise ValidationError(_('El monto a aplicar debe ser mayor o igual a cero.'))

    def action_apply_max(self):
        """Aplica el monto máximo disponible."""
        self.ensure_one()
        remaining_residual = self.wizard_id.residual_amount - self.wizard_id.total_to_apply + self.amount_to_apply
        self.amount_to_apply = min(self.available_amount, remaining_residual)

    def action_clear(self):
        """Limpia el monto a aplicar."""
        self.ensure_one()
        self.amount_to_apply = 0.0


class ApplyAdvanceWizard(models.TransientModel):
    """Wizard para aplicar anticipos de cliente a una factura"""
    _name = 'apply.advance.wizard'
    _description = 'Wizard de Aplicación de Abono/Anticipo de Cliente'

    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='move_id.partner_id',
        readonly=True
    )
    invoice_amount = fields.Monetary(
        string='Monto de Factura',
        related='move_id.amount_total',
        readonly=True
    )
    residual_amount = fields.Monetary(
        string='Saldo Pendiente',
        related='move_id.amount_residual',
        readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='move_id.currency_id',
        readonly=True
    )
    line_ids = fields.One2many(
        'apply.advance.wizard.line',
        'wizard_id',
        string='Abonos/Anticipos Disponibles'
    )
    total_to_apply = fields.Monetary(
        string='Total a Aplicar',
        compute='_compute_total_to_apply',
        currency_field='currency_id',
        help='Total de Abonos/Anticipos a aplicar'
    )
    remaining_after_apply = fields.Monetary(
        string='Saldo después de aplicar',
        compute='_compute_total_to_apply',
        currency_field='currency_id',
        help='Saldo pendiente después de aplicar los Abonos/Anticipos'
    )
    reclass_date = fields.Date(
        string='Fecha del Asiento',
        default=fields.Date.context_today,
        required=True,
        help='Fecha que se usará para el asiento de reclasificación'
    )

    @api.depends('line_ids.amount_to_apply')
    def _compute_total_to_apply(self):
        """Calcula el total a aplicar y el saldo restante."""
        for wizard in self:
            total = sum(wizard.line_ids.mapped('amount_to_apply'))
            wizard.total_to_apply = total
            wizard.remaining_after_apply = wizard.residual_amount - total

    @api.onchange('move_id')
    def _onchange_move_id(self):
        """Determina la fecha del asiento según la configuración."""
        if self.move_id:
            date_source = self._get_config('reclass_date_source', 'invoice')
            if date_source == 'invoice':
                self.reclass_date = self.move_id.invoice_date or fields.Date.today()
            else:
                self.reclass_date = fields.Date.today()

    def action_apply_advances(self):
        """
        Aplica los anticipos seleccionados a la factura.
        
        Crea un asiento de reclasificación por cada anticipo aplicado
        y los concilia con la factura.
        
        Returns:
            dict: Acción para volver a la factura
            
        Raises:
            UserError: Si hay errores en la aplicación
        """
        self.ensure_one()
        
        lines_to_apply = self.line_ids.filtered(lambda l: l.amount_to_apply > 0)
        
        if not lines_to_apply:
            raise UserError(_('Debe seleccionar al menos un Abono/Anticipo con monto mayor a cero.'))
        
        # Validar que el total no exceda el residual
        if self.total_to_apply > self.residual_amount:
            raise UserError(_(
                'El total a aplicar (%s) excede el saldo pendiente de la factura (%s).',
                self.total_to_apply, self.residual_amount
            ))
        
        # Validación adicional: Advertencia si el monto es muy pequeño (< 1% del anticipo)
        for line in lines_to_apply:
            if line.amount_to_apply > 0 and line.available_amount > 0:
                percentage = (line.amount_to_apply / line.available_amount) * 100
                if percentage < 1:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.warning(
                        'Monto muy pequeño aplicado: %s (%s%%) del Abono/Anticipo %s',
                        line.amount_to_apply, percentage, line.payment_id.name
                    )
        
        # Validación adicional: Advertencia si se aplica más del 90% del anticipo
        for line in lines_to_apply:
            if line.amount_to_apply > 0 and line.available_amount > 0:
                percentage = (line.amount_to_apply / line.available_amount) * 100
                if percentage > 90 and percentage < 100:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.info(
                        'Aplicando más del 90%% del Abono/Anticipo %s: %s%% restante',
                        line.payment_id.name, 100 - percentage
                    )
        
        # Obtener configuración
        journal = self._get_reclass_journal()
        
        # Obtener cuenta según el tipo de factura
        if self.move_id.move_type == 'out_invoice':
            # Para facturas de cliente: cuenta por cobrar
            ar_account = self.move_id.partner_id.property_account_receivable_id
            if not ar_account:
                raise UserError(_(
                    'El cliente "%s" no tiene configurada una cuenta por cobrar.',
                    self.move_id.partner_id.name
                ))
        elif self.move_id.move_type == 'in_invoice':
            # Para facturas de proveedor: cuenta por pagar
            ar_account = self.move_id.partner_id.property_account_payable_id
            if not ar_account:
                raise UserError(_(
                    'El proveedor "%s" no tiene configurada una cuenta por pagar.',
                    self.move_id.partner_id.name
                ))
        else:
            raise UserError(_('Tipo de factura no válido para aplicar Abonos/Anticipos.'))
        
        # Procesar cada línea de anticipo
        created_links = []
        for line in lines_to_apply:
            advance_account = line.payment_id.advance_account_id
            
            if not advance_account:
                raise UserError(_(
                    'El Abono/Anticipo %s no tiene cuenta de Abono/Anticipo configurada.',
                    line.payment_id.name
                ))
            
            # Crear asiento de reclasificación
            reclass_move = self._create_reclass_move(
                line.payment_id,
                line.amount_to_apply,
                journal,
                advance_account,
                ar_account
            )
            
            # Crear enlace de trazabilidad
            link = self.env['account.advance.link'].create({
                'payment_id': line.payment_id.id,
                'move_id': self.move_id.id,
                'reclass_move_id': reclass_move.id,
                'amount': line.amount_to_apply,
            })
            created_links.append(link)
            
            # Conciliar las líneas AR
            self._reconcile_lines(reclass_move, line.amount_to_apply)
            
            # Registrar en chatter del pago
            line.payment_id.message_post(
                body=_('Abono/Anticipo aplicado a factura %s: %s %s (Asiento: %s)',
                       self.move_id.name, line.amount_to_apply, 
                       self.move_id.currency_id.symbol, reclass_move.name)
            )
        
        # Registrar en chatter de la factura
        self.move_id.message_post(
            body=_('Abono(s)/Anticipo(s) aplicado(s): %s %s. Asientos: %s',
                   self.total_to_apply,
                   self.currency_id.symbol,
                   ', '.join([link.reclass_move_id.name for link in created_links]))
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura'),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_reclass_move(self, payment, amount, journal, advance_account, ar_account):
        """
        Crea el asiento de reclasificación según el tipo de factura.
        
        Para clientes: De pasivo (anticipo) a CxC (asset_receivable)
        Para proveedores: De activo (anticipo) a CxP (liability_payable)
        
        Args:
            payment: account.payment - El anticipo
            amount: float - Monto a reclasificar
            journal: account.journal - Diario para el asiento
            advance_account: account.account - Cuenta de anticipo
            ar_account: account.account - Cuenta por cobrar/pagar
            
        Returns:
            account.move: El asiento de reclasificación creado y publicado
        """
        # Determinar fecha según configuración
        date_source = self._get_config('reclass_date_source', 'invoice')
        if date_source == 'invoice':
            move_date = self.move_id.invoice_date or fields.Date.today()
        else:
            move_date = self.reclass_date
        
        # Determinar tipo de cuenta según el tipo de factura
        if self.move_id.move_type == 'out_invoice':
            # Clientes: Débito anticipo (pasivo), Crédito CxC (activo)
            line_debit = {
                'account_id': advance_account.id,
                'partner_id': self.move_id.partner_id.id,
                'debit': amount,
                'credit': 0.0,
                'name': _('Reclasificación Abono/Anticipo %s', payment.name),
            }
            line_credit = {
                'account_id': ar_account.id,
                'partner_id': self.move_id.partner_id.id,
                'debit': 0.0,
                'credit': amount,
                'name': _('Aplicación a factura %s', self.move_id.name),
            }
        elif self.move_id.move_type == 'in_invoice':
            # Proveedores: Crédito anticipo (activo), Débito CxP (pasivo)
            line_debit = {
                'account_id': ar_account.id,
                'partner_id': self.move_id.partner_id.id,
                'debit': amount,
                'credit': 0.0,
                'name': _('Aplicación a factura %s', self.move_id.name),
            }
            line_credit = {
                'account_id': advance_account.id,
                'partner_id': self.move_id.partner_id.id,
                'debit': 0.0,
                'credit': amount,
                'name': _('Reclasificación Abono/Anticipo %s', payment.name),
            }
        else:
            raise UserError(_('Tipo de factura no válido para reclasificación.'))
        
        # Preparar valores del asiento
        move_vals = {
            'move_type': 'entry',
            'date': move_date,
            'journal_id': journal.id,
            'company_id': self.move_id.company_id.id,
            'ref': _('Reclasificación de Abono/Anticipo %s - Factura %s', payment.name, self.move_id.name),
            'line_ids': [
                (0, 0, line_debit),
                (0, 0, line_credit),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        
        return move

    def _reconcile_lines(self, reclass_move, amount):
        """
        Concilia la línea AR/AP del asiento de reclasificación con la factura.
        
        Args:
            reclass_move: account.move - Asiento de reclasificación
            amount: float - Monto a conciliar
        """
        # Determinar tipo de cuenta según el tipo de factura
        if self.move_id.move_type == 'out_invoice':
            account_type = 'asset_receivable'
            # Para clientes: factura tiene débito, reclass tiene crédito
            invoice_filter = lambda l: l.debit > 0
            reclass_filter = lambda l: l.credit > 0
        elif self.move_id.move_type == 'in_invoice':
            account_type = 'liability_payable'
            # Para proveedores: factura tiene crédito, reclass tiene débito
            invoice_filter = lambda l: l.credit > 0
            reclass_filter = lambda l: l.debit > 0
        else:
            return
        
        # Buscar línea AR/AP de la factura (no conciliada)
        invoice_line = self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == account_type and
                      l.partner_id == self.move_id.partner_id and
                      invoice_filter(l) and
                      not l.reconciled
        )[:1]
        
        # Buscar línea AR/AP del asiento de reclasificación
        reclass_line = reclass_move.line_ids.filtered(
            lambda l: l.account_id.account_type == account_type and
                      l.partner_id == self.move_id.partner_id and
                      reclass_filter(l)
        )[:1]
        
        if invoice_line and reclass_line:
            try:
                (invoice_line + reclass_line).reconcile()
            except Exception as e:
                _logger.warning('Error al conciliar líneas de anticipo: %s', str(e))
                # Intentar conciliación parcial manual
                self._create_partial_reconcile(invoice_ar_line, reclass_ar_line, amount)

    def _create_partial_reconcile(self, debit_line, credit_line, amount):
        """
        Crea una conciliación parcial manualmente.
        
        Args:
            debit_line: account.move.line - Línea de débito (factura)
            credit_line: account.move.line - Línea de crédito (reclasificación)
            amount: float - Monto a conciliar
        """
        try:
            company_currency = self.move_id.company_id.currency_id
            
            reconcile_vals = {
                'debit_move_id': debit_line.id,
                'credit_move_id': credit_line.id,
                'amount': amount,
            }
            
            if self.move_id.currency_id != company_currency:
                reconcile_vals.update({
                    'debit_amount_currency': amount,
                    'credit_amount_currency': amount,
                    'currency_id': self.move_id.currency_id.id,
                })
            
            self.env['account.partial.reconcile'].create(reconcile_vals)
        except Exception as e:
            _logger.error('Error al crear conciliación parcial: %s', str(e))

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    def _get_config(self, param_name, default=None):
        """
        Obtiene un parámetro de configuración del módulo.
        
        Args:
            param_name: str - Nombre del parámetro (sin prefijo)
            default: Valor por defecto
            
        Returns:
            str: Valor del parámetro
        """
        full_param = f'gts_customer_advance.{param_name}'
        return self.env['ir.config_parameter'].sudo().get_param(full_param, default)

    def _get_reclass_journal(self):
        """
        Obtiene el diario para asientos de reclasificación.
        
        Returns:
            account.journal: Diario configurado o diario general por defecto
            
        Raises:
            UserError: Si no se encuentra un diario válido
        """
        journal_id = self._get_config('reclass_journal_id')
        
        if journal_id:
            try:
                journal = self.env['account.journal'].browse(int(journal_id))
                if journal.exists() and journal.company_id == self.move_id.company_id:
                    return journal
            except (ValueError, TypeError):
                pass
        
        # Buscar diario general por defecto
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.move_id.company_id.id)
        ], limit=1)
        
        if not journal:
            raise UserError(_(
                'No se encontró un diario general para crear el asiento de reclasificación. '
                'Configure uno en Contabilidad → Configuración → Ajustes.'
            ))
        
        return journal


# =============================================================================
# WIZARD: Aplicar un anticipo a múltiples facturas (desde el pago)
# =============================================================================

class ApplyAdvanceToInvoicesWizardLine(models.TransientModel):
    """Líneas del wizard para seleccionar facturas a las que aplicar el anticipo"""
    _name = 'apply.advance.to.invoices.wizard.line'
    _description = 'Línea de Wizard de Aplicación de Abono/Anticipo a Facturas'

    wizard_id = fields.Many2one(
        'apply.advance.to.invoices.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        readonly=True
    )
    invoice_date = fields.Date(
        string='Fecha',
        related='move_id.invoice_date',
        readonly=True
    )
    invoice_name = fields.Char(
        string='Número',
        related='move_id.name',
        readonly=True
    )
    amount_total = fields.Monetary(
        string='Total',
        related='move_id.amount_total',
        readonly=True,
        currency_field='currency_id'
    )
    amount_residual = fields.Monetary(
        string='Saldo Pendiente',
        related='move_id.amount_residual',
        readonly=True,
        currency_field='currency_id'
    )
    amount_to_apply = fields.Monetary(
        string='Monto a Aplicar',
        currency_field='currency_id',
        help='Monto del Abono/Anticipo a aplicar a esta factura'
    )
    max_amount = fields.Monetary(
        string='Máximo Aplicable',
        currency_field='currency_id',
        readonly=True,
        help='Máximo que se puede aplicar (menor entre saldo del Abono/Anticipo y residual de factura)'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='move_id.currency_id',
        readonly=True
    )

    @api.constrains('amount_to_apply', 'max_amount')
    def _check_amount_to_apply(self):
        """Valida que el monto a aplicar no exceda el máximo permitido."""
        for line in self:
            if line.amount_to_apply > line.max_amount:
                raise ValidationError(_(
                    'El monto a aplicar (%s) no puede ser mayor que el máximo permitido (%s) para la factura %s.',
                    line.amount_to_apply, line.max_amount, line.move_id.name
                ))
            if line.amount_to_apply < 0:
                raise ValidationError(_('El monto a aplicar debe ser mayor o igual a cero.'))


class ApplyAdvanceToInvoicesWizard(models.TransientModel):
    """Wizard para aplicar un anticipo a múltiples facturas"""
    _name = 'apply.advance.to.invoices.wizard'
    _description = 'Wizard de Aplicación de Abono/Anticipo a Facturas'

    payment_id = fields.Many2one(
        'account.payment',
        string='Abono/Anticipo',
        required=True,
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='payment_id.partner_id',
        readonly=True
    )
    advance_amount = fields.Monetary(
        string='Monto del Abono/Anticipo',
        related='payment_id.amount',
        readonly=True
    )
    available_amount = fields.Monetary(
        string='Saldo Disponible',
        related='payment_id.advance_available_amount',
        readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='payment_id.currency_id',
        readonly=True
    )
    line_ids = fields.One2many(
        'apply.advance.to.invoices.wizard.line',
        'wizard_id',
        string='Facturas Pendientes'
    )
    total_to_apply = fields.Monetary(
        string='Total a Aplicar',
        compute='_compute_total_to_apply',
        currency_field='currency_id'
    )
    remaining_after_apply = fields.Monetary(
        string='Saldo después de aplicar',
        compute='_compute_total_to_apply',
        currency_field='currency_id'
    )

    @api.depends('line_ids.amount_to_apply', 'available_amount')
    def _compute_total_to_apply(self):
        """Calcula el total a aplicar y el saldo restante."""
        for wizard in self:
            total = sum(wizard.line_ids.mapped('amount_to_apply'))
            wizard.total_to_apply = total
            wizard.remaining_after_apply = wizard.available_amount - total

    def action_apply_to_invoices(self):
        """
        Aplica el anticipo a las facturas seleccionadas.
        
        Returns:
            dict: Acción para volver al pago
            
        Raises:
            UserError: Si hay errores en la aplicación
        """
        self.ensure_one()
        
        lines_to_apply = self.line_ids.filtered(lambda l: l.amount_to_apply > 0)
        
        if not lines_to_apply:
            raise UserError(_('Debe seleccionar al menos una factura con monto mayor a cero.'))
        
        # Validar que el total no exceda el saldo disponible
        if self.total_to_apply > self.available_amount:
            raise UserError(_(
                'El total a aplicar (%s) excede el saldo disponible del Abono/Anticipo (%s).',
                self.total_to_apply, self.available_amount
            ))
        
        # Aplicar a cada factura usando el wizard estándar
        for line in lines_to_apply:
            # Crear wizard de aplicación para esta factura
            wizard = self.env['apply.advance.wizard'].create({
                'move_id': line.move_id.id,
            })
            
            # Crear línea para el anticipo actual
            self.env['apply.advance.wizard.line'].create({
                'wizard_id': wizard.id,
                'payment_id': self.payment_id.id,
                'available_amount': self.payment_id.advance_available_amount,
                'amount_to_apply': line.amount_to_apply,
            })
            
            # Aplicar
            wizard.action_apply_advances()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Abono/Anticipo'),
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
