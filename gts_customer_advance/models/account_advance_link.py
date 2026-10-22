# -*- coding: utf-8 -*-
"""
Modelo para trazabilidad de aplicaciones de anticipos.

Este modelo registra cada aplicación de un anticipo a una factura,
incluyendo el asiento de reclasificación generado y la información
de auditoría.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountAdvanceLink(models.Model):
    """Modelo para trazabilidad de aplicaciones de anticipos"""
    _name = 'account.advance.link'
    _inherit = ['advance.cancel.mixin']
    _description = 'Enlace de Aplicación de Anticipo'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    payment_id = fields.Many2one(
        'account.payment',
        string='Anticipo',
        required=True,
        ondelete='cascade',
        index=True,
        help='Pago marcado como anticipo'
    )
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        ondelete='cascade',
        index=True,
        help='Factura a la que se aplicó el anticipo'
    )
    reclass_move_id = fields.Many2one(
        'account.move',
        string='Asiento de Reclasificación',
        required=True,
        ondelete='restrict',
        index=True,
        help='Asiento contable de reclasificación de pasivo a CxC'
    )
    amount = fields.Monetary(
        string='Monto Aplicado',
        required=True,
        currency_field='currency_id',
        help='Monto del anticipo aplicado a esta factura'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='move_id.currency_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='move_id.company_id',
        store=True,
        readonly=True,
        index=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='move_id.partner_id',
        store=True,
        readonly=True,
        index=True
    )
    applied_date = fields.Datetime(
        string='Fecha de Aplicación',
        default=fields.Datetime.now,
        readonly=True,
        help='Fecha y hora en que se aplicó el anticipo'
    )
    applied_user_id = fields.Many2one(
        'res.users',
        string='Aplicado por',
        default=lambda self: self.env.user,
        readonly=True,
        help='Usuario que aplicó el anticipo'
    )
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True
    )
    state = fields.Selection([
        ('applied', 'Aplicado'),
        ('reversed', 'Revertido'),
    ], string='Estado', default='applied', readonly=True)
    advance_cancel_allowed = fields.Boolean(
        compute='_compute_advance_cancel_allowed',
    )

    # Campos relacionados para información adicional
    payment_date = fields.Date(
        string='Fecha del Anticipo',
        related='payment_id.date',
        store=True,
        readonly=True
    )
    invoice_date = fields.Date(
        string='Fecha de Factura',
        related='move_id.invoice_date',
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('create_date')
    def _compute_advance_cancel_allowed(self):
        for link in self:
            link.advance_cancel_allowed = link._advance_cancel_allowed_for_record(link)

    @api.depends('payment_id.name', 'move_id.name', 'amount', 'currency_id.symbol')
    def _compute_display_name(self):
        """
        Genera nombre legible para el registro.
        
        Formato: "PAGO-001 → FAC-001 (100.00 $)"
        """
        for record in self:
            payment_name = record.payment_id.name or _('Sin nombre')
            move_name = record.move_id.name or _('Sin nombre')
            symbol = record.currency_id.symbol or ''
            record.display_name = f'{payment_name} → {move_name} ({record.amount:,.2f} {symbol})'

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------

    @api.constrains('amount')
    def _check_amount(self):
        """Valida que el monto sea positivo."""
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('El monto aplicado debe ser mayor que cero.'))

    @api.constrains('payment_id', 'move_id')
    def _check_same_partner(self):
        """Valida que el anticipo y la factura sean del mismo cliente."""
        for record in self:
            if record.payment_id.partner_id != record.move_id.partner_id:
                raise ValidationError(_(
                    'El anticipo y la factura deben ser del mismo cliente.'
                ))

    @api.constrains('payment_id', 'move_id')
    def _check_same_company(self):
        """Valida que el anticipo y la factura sean de la misma compañía."""
        for record in self:
            if record.payment_id.company_id != record.move_id.company_id:
                raise ValidationError(_(
                    'El anticipo y la factura deben ser de la misma compañía.'
                ))

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def action_view_payment(self):
        """
        Abre el formulario del pago anticipo.
        
        Returns:
            dict: Acción para abrir el formulario
        """
        self.ensure_one()
        return {
            'name': _('Anticipo'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_move(self):
        """
        Abre el formulario de la factura.
        
        Returns:
            dict: Acción para abrir el formulario
        """
        self.ensure_one()
        return {
            'name': _('Factura'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_reclass_move(self):
        """
        Abre el formulario del asiento de reclasificación.
        
        Returns:
            dict: Acción para abrir el formulario
        """
        self.ensure_one()
        return {
            'name': _('Asiento de Reclasificación'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.reclass_move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reverse(self):
        """
        Abre el wizard para revertir la aplicación de este anticipo.
        
        Returns:
            dict: Acción para abrir el wizard de reversión
        """
        self.ensure_one()
        
        if self.state == 'reversed':
            raise UserError(_('Esta aplicación ya fue revertida.'))

        self._advance_check_cancel_allowed(self, _('revertir'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Revertir Aplicación de Anticipo'),
            'res_model': 'reverse.advance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_link_id': self.id,
                'default_reverse_date': fields.Date.today(),
            }
        }

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def _reverse_advance_application(self):
        """
        Revierte la aplicación de un anticipo (usado al cancelar factura).
        
        Crea un asiento reverso de la reclasificación original y actualiza
        el estado del enlace. No elimina el registro para mantener trazabilidad.
        
        Raises:
            UserError: Si el asiento de reclasificación no está en estado válido
        """
        self.ensure_one()

        self._advance_check_cancel_allowed(self, _('revertir'))

        if self.state == 'reversed':
            _logger.warning('Intento de revertir enlace ya revertido: %s', self.display_name)
            return
        
        reclass_move = self.reclass_move_id
        
        # Validar estado del asiento de reclasificación
        if not reclass_move:
            raise UserError(_('No se encontró el asiento de reclasificación.'))
        
        if reclass_move.state == 'cancel':
            _logger.warning(
                'Asiento de reclasificación %s ya está cancelado, marcando enlace como revertido',
                reclass_move.name
            )
            self.state = 'reversed'
            return
        
        # Crear asiento reverso (invertir débitos y créditos)
        reverse_move_vals = {
            'move_type': 'entry',
            'date': fields.Date.context_today(self),
            'journal_id': reclass_move.journal_id.id,
            'company_id': reclass_move.company_id.id,
            'ref': _('Reversa de reclasificación %s - Factura %s', 
                     reclass_move.name or reclass_move.ref, self.move_id.name),
            'line_ids': [],
        }
        
        # Invertir las líneas
        for line in reclass_move.line_ids:
            reverse_move_vals['line_ids'].append((0, 0, {
                'account_id': line.account_id.id,
                'partner_id': line.partner_id.id,
                'debit': line.credit,  # Invertir
                'credit': line.debit,  # Invertir
                'currency_id': line.currency_id.id if line.currency_id else False,
                'amount_currency': -line.amount_currency if line.amount_currency else 0.0,
                'name': _('Reversa: %s', line.name or ''),
            }))
        
        reverse_move = self.env['account.move'].create(reverse_move_vals)
        reverse_move.action_post()
        
        # Intentar desconciliar las líneas originales
        try:
            self._unreconcile_lines()
        except Exception as e:
            _logger.warning('No se pudo desconciliar líneas: %s', str(e))
        
        # Registrar en chatter
        self.move_id.message_post(
            body=_('Aplicación de anticipo revertida: %s %s (Asiento reverso: %s)',
                   self.amount, self.currency_id.symbol, reverse_move.name)
        )
        
        self.payment_id.message_post(
            body=_('Aplicación revertida de factura %s: %s %s',
                   self.move_id.name, self.amount, self.currency_id.symbol)
        )
        
        # Marcar como revertido en lugar de eliminar (mantener trazabilidad)
        self.state = 'reversed'
        
        _logger.info(
            'Aplicación de anticipo revertida: %s (reverso: %s)',
            self.display_name, reverse_move.name
        )

    def _unreconcile_lines(self):
        """
        Intenta desconciliar las líneas AR del asiento de reclasificación.
        
        Este método es best-effort y no falla si no puede desconciliar.
        """
        reclass_move = self.reclass_move_id
        
        # Buscar líneas AR conciliadas del asiento de reclasificación
        ar_lines = reclass_move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and l.reconciled
        )
        
        for line in ar_lines:
            if line.matched_credit_ids:
                line.matched_credit_ids.unlink()
            if line.matched_debit_ids:
                line.matched_debit_ids.unlink()
