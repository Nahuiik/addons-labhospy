# -*- coding: utf-8 -*-
"""
Extensión de account.move para gestión de anticipos de clientes.

Este módulo permite detectar anticipos disponibles en facturas de cliente
y aplicarlos mediante un wizard interactivo.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'advance.cancel.mixin']

    advance_applied_amount = fields.Monetary(
        string='Total Abonos/Anticipos Aplicados',
        compute='_compute_advance_applied_amount',
        store=True,
        currency_field='currency_id',
        help='Total de Abonos/Anticipos aplicados a esta factura'
    )
    has_available_advances = fields.Boolean(
        string='Tiene Abonos/Anticipos Disponibles',
        compute='_compute_has_available_advances',
        store=True,  # Agregado store=True para consistencia
        help='Indica si el cliente tiene Abonos/Anticipos disponibles que se pueden aplicar'
    )
    available_advances_amount = fields.Monetary(
        string='Monto de Abonos/Anticipos Disponibles',
        compute='_compute_has_available_advances',
        store=True,
        currency_field='currency_id',
        help='Monto total de Abonos/Anticipos disponibles para este cliente'
    )
    advance_link_ids = fields.One2many(
        'account.advance.link',
        'move_id',
        string='Aplicaciones de Abono/Anticipo',
        readonly=True
    )
    available_advances_count = fields.Integer(
        string='Cantidad de Abonos/Anticipos Disponibles',
        compute='_compute_has_available_advances',
        store=True,  # Agregado store=True para consistencia
        help='Número de Abonos/Anticipos disponibles para este cliente'
    )
    dte_accepted_for_advances = fields.Boolean(
        string='DTE Aceptado para Abonos/Anticipos',
        compute='_compute_dte_accepted_for_advances',
        store=False,
        help='Indica si el DTE está aceptado por hacienda (solo si sv_electronic_invoicing está instalado)'
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    
    def _compute_dte_accepted_for_advances(self):
        """
        Calcula si el DTE está aceptado para permitir aplicar anticipos.
        Solo funciona si el módulo sv_electronic_invoicing está instalado.
        
        Para facturas de proveedor (in_invoice), siempre permite anticipos sin validar DTE.
        Para facturas de cliente (out_invoice), requiere que el DTE esté aceptado.
        
        Si el módulo no está instalado, siempre retorna True para permitir anticipos.
        
        Nota: No usa @api.depends porque el campo puede no existir si el módulo
        sv_electronic_invoicing no está instalado.
        """
        for move in self:
            # Para facturas de proveedor, siempre permitir anticipos sin validar DTE
            if move.move_type == 'in_invoice':
                move.dte_accepted_for_advances = True
                continue
            
            # Para facturas de cliente, validar DTE si el módulo está instalado
            # Verificar si el campo existe (módulo sv_electronic_invoicing instalado)
            if hasattr(move, 'l10n_sv_electronic_dte_state'):
                # Si el campo existe pero está vacío o no aplica (no es DTE), permitir anticipos
                if not move.l10n_sv_electronic_dte_state:
                    move.dte_accepted_for_advances = True
                else:
                    # Solo permitir si está aceptado
                    move.dte_accepted_for_advances = move.l10n_sv_electronic_dte_state == 'accepted'
            else:
                # Si el módulo no está instalado, siempre permitir anticipos
                move.dte_accepted_for_advances = True

    @api.depends('advance_link_ids.amount', 'advance_link_ids.currency_id')
    def _compute_advance_applied_amount(self):
        """
        Calcula el total de anticipos aplicados a esta factura.
        
        Solo suma los enlaces que tienen la misma moneda que la factura
        para evitar inconsistencias.
        """
        for move in self:
            if move.advance_link_ids:
                # Optimización: filtrar en una sola pasada
                total = sum(
                    link.amount for link in move.advance_link_ids 
                    if link.currency_id == move.currency_id
                )
                move.advance_applied_amount = total
            else:
                move.advance_applied_amount = 0.0

    @api.depends('partner_id', 'company_id', 'move_type', 'state', 'currency_id', 'amount_residual')
    def _compute_has_available_advances(self):
        """
        Calcula si hay anticipos disponibles para este cliente o proveedor.
        
        Optimizado para:
        - Solo calcular para facturas de cliente o proveedor publicadas con saldo pendiente
        - Usar el campo almacenado advance_available_amount para filtrar en SQL
        - Evitar logs excesivos en producción
        """
        Payment = self.env['account.payment']
        
        # Filtrar solo las facturas que necesitan cálculo (clientes y proveedores)
        invoices_to_compute = self.filtered(
            lambda m: m.move_type in ('out_invoice', 'in_invoice') and 
                      m.state == 'posted' and 
                      m.partner_id and 
                      m.company_id and
                      m.amount_residual > 0
        )
        
        # Inicializar todos los registros
        for move in self:
            move.has_available_advances = False
            move.available_advances_amount = 0.0
            move.available_advances_count = 0
        
        # Procesar solo las facturas relevantes
        if invoices_to_compute:
            # Agrupar por (partner_id, company_id, currency_id) para optimizar búsquedas
            partner_groups = {}
            for move in invoices_to_compute:
                key = (move.partner_id.id, move.company_id.id, move.currency_id.id)
                if key not in partner_groups:
                    partner_groups[key] = []
                partner_groups[key].append(move)
            
            # Buscar anticipos para cada grupo
            for (partner_id, company_id, currency_id), moves in partner_groups.items():
                # Determinar el tipo de partner según el tipo de factura
                partner_type = 'customer' if moves[0].move_type == 'out_invoice' else 'supplier'
                available_advances = Payment._get_available_advances_for_partner(
                    partner_id, company_id, currency_id, partner_type=partner_type
                )
                
                if available_advances:
                    total_available = sum(available_advances.mapped('advance_available_amount'))
                    count = len(available_advances)
                    
                    for move in moves:
                        move.available_advances_amount = total_available
                        move.has_available_advances = total_available > 0
                        move.available_advances_count = count

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    @api.model
    def _recompute_available_advances_all(self):
        """
        Método helper para forzar el recálculo de anticipos disponibles en todas las facturas.
        Útil después de cambios en estados de anticipos o actualizaciones del módulo.
        """
        invoices = self.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ])
        if invoices:
            invoices._compute_has_available_advances()
            self.env.cr.commit()
        return len(invoices)

    def action_open_apply_advance_wizard(self):
        """
        Abre el wizard para aplicar anticipos a esta factura.
        
        Valida que la factura cumpla con los requisitos antes de abrir el wizard.
        
        Returns:
            dict: Acción para abrir el wizard
            
        Raises:
            UserError: Si la factura no cumple con los requisitos
        """
        self.ensure_one()
        
        # Validaciones
        if self.move_type not in ('out_invoice', 'in_invoice'):
            raise UserError(_('Solo se pueden aplicar Abonos/Anticipos a facturas de cliente o proveedor.'))
        
        if self.state != 'posted':
            raise UserError(_('La factura debe estar publicada para aplicar Abonos/Anticipos.'))
        
        if not self.partner_id:
            raise UserError(_('La factura debe tener un contacto asignado.'))
        
        if self.amount_residual <= 0:
            raise UserError(_('La factura ya está completamente pagada.'))

        partner_type = 'customer' if self.move_type == 'out_invoice' else 'supplier'
        partner_label = _('cliente') if partner_type == 'customer' else _('proveedor')

        # Validar que el partner tenga la cuenta contable correspondiente
        if partner_type == 'customer':
            if not self.partner_id.property_account_receivable_id:
                raise UserError(_(
                    'El cliente "%s" no tiene configurada una cuenta por cobrar.',
                    self.partner_id.name
                ))
        elif not self.partner_id.property_account_payable_id:
            raise UserError(_(
                'El proveedor "%s" no tiene configurada una cuenta por pagar.',
                self.partner_id.name
            ))
        
        # Validación adicional: Verificar que la factura no sea anterior al anticipo más antiguo
        Payment = self.env['account.payment']
        oldest_advance = Payment.search([
            ('is_advance', '=', True),
            ('partner_type', '=', partner_type),
            ('partner_id', '=', self.partner_id.id),
            ('company_id', '=', self.company_id.id),
            ('currency_id', '=', self.currency_id.id),
            ('advance_available_amount', '>', 0)
        ], order='date asc', limit=1)
        
        if oldest_advance and self.invoice_date and oldest_advance.date:
            if self.invoice_date < oldest_advance.date:
                # Advertencia pero no bloquea (configurable)
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(
                    'Factura %s (%s) es anterior al anticipo más antiguo %s (%s)',
                    self.name, self.invoice_date, oldest_advance.name, oldest_advance.date
                )
        
        # Validación de moneda: Los anticipos deben estar en la misma moneda
        # (ya se valida en _get_available_advances_for_partner, pero agregamos mensaje más claro)
        
        # Obtener anticipos disponibles
        available_advances = Payment._get_available_advances_for_partner(
            self.partner_id.id,
            self.company_id.id,
            self.currency_id.id,
            partner_type=partner_type,
        )
        
        if not available_advances:
            raise UserError(_(
                'No hay Abonos/Anticipos disponibles para este %s.',
                partner_label,
            ))
        
        # Crear wizard con los anticipos disponibles
        wizard = self.env['apply.advance.wizard'].create({
            'move_id': self.id,
        })
        
        # Crear líneas del wizard para cada anticipo disponible
        remaining_residual = self.amount_residual
        for advance in available_advances:
            # Calcular monto máximo aplicable (mínimo entre saldo del anticipo y residual restante)
            max_amount = min(advance.advance_available_amount, remaining_residual)
            
            self.env['apply.advance.wizard.line'].create({
                'wizard_id': wizard.id,
                'payment_id': advance.id,
                'available_amount': advance.advance_available_amount,
                'amount_to_apply': max_amount if remaining_residual > 0 else 0.0,
            })
            
            # Reducir el residual restante para la siguiente línea
            remaining_residual -= max_amount
            if remaining_residual <= 0:
                remaining_residual = 0
        
        wizard_title = (
            _('Aplicar Abono/Anticipo de Cliente')
            if partner_type == 'customer'
            else _('Aplicar Abono/Anticipo de Proveedor')
        )
        return {
            'name': wizard_title,
            'type': 'ir.actions.act_window',
            'res_model': 'apply.advance.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _advance_check_move_cancel(self):
        AdvanceLink = self.env['account.advance.link']
        for move in self:
            if move.advance_link_ids:
                self._advance_check_cancel_allowed(move, _('cancelar'))
            reclass_links = AdvanceLink.search([
                ('reclass_move_id', '=', move.id),
            ])
            if reclass_links:
                self._advance_check_cancel_allowed(reclass_links, _('cancelar'))

    def button_cancel(self):
        """
        Sobrescribe para revertir anticipos aplicados al cancelar factura.
        
        Crea asientos reversos para cada aplicación de anticipo y elimina
        los registros de enlace.
        
        Returns:
            bool: Resultado de super().button_cancel()
        """
        self._advance_check_move_cancel()
        # Revertir anticipos antes de cancelar
        for move in self:
            if move.advance_link_ids:
                # Revertir cada aplicación de anticipo
                for link in move.advance_link_ids:
                    try:
                        link._reverse_advance_application()
                    except Exception as e:
                        _logger.error(
                            'Error al revertir aplicación de anticipo %s: %s',
                            link.display_name, str(e)
                        )
                        raise UserError(_(
                            'Error al revertir la aplicación de Abono/Anticipo: %s',
                            str(e)
                        ))
        
        return super().button_cancel()

    def action_view_advance_links(self):
        """
        Abre una vista con las aplicaciones de anticipo de esta factura.
        
        Returns:
            dict: Acción para abrir la vista de enlaces
        """
        self.ensure_one()
        return {
            'name': _('Abonos/Anticipos Aplicados'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.advance.link',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
            'context': {'create': False},
        }