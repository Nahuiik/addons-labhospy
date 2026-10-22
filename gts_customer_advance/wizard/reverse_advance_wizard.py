# -*- coding: utf-8 -*-
"""
Wizard para revertir aplicaciones de anticipos.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ReverseAdvanceWizard(models.TransientModel):
    """Wizard para revertir aplicaciones de anticipos"""
    _name = 'reverse.advance.wizard'
    _description = 'Wizard de Reversión de Abono/Anticipo'

    link_id = fields.Many2one(
        'account.advance.link',
        string='Aplicación de Abono/Anticipo',
        required=True,
        readonly=True
    )
    reason = fields.Text(
        string='Motivo de Reversión',
        required=True,
        help='Explique el motivo por el cual se revierte esta aplicación'
    )
    reverse_date = fields.Date(
        string='Fecha de Reversión',
        default=fields.Date.today,
        required=True
    )
    reverse_partial = fields.Boolean(
        string='Reversión Parcial',
        default=False,
        help='Si está marcado, puede revertir solo una parte del monto aplicado'
    )
    reverse_amount = fields.Monetary(
        string='Monto a Revertir',
        currency_field='currency_id',
        help='Monto parcial a revertir (dejar vacío para revertir todo)'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='link_id.currency_id',
        readonly=True
    )
    original_amount = fields.Monetary(
        string='Monto Original',
        currency_field='currency_id',
        related='link_id.amount',
        readonly=True
    )

    @api.constrains('reverse_amount', 'reverse_partial', 'original_amount')
    def _check_reverse_amount(self):
        """Valida el monto a revertir"""
        for wizard in self:
            if wizard.reverse_partial:
                if not wizard.reverse_amount or wizard.reverse_amount <= 0:
                    raise ValidationError(_('El monto a revertir debe ser mayor que cero.'))
                if wizard.reverse_amount > wizard.original_amount:
                    raise ValidationError(_(
                        'El monto a revertir (%s) no puede ser mayor que el monto original (%s).',
                        wizard.reverse_amount, wizard.original_amount
                    ))

    def action_reverse(self):
        """Ejecuta la reversión"""
        self.ensure_one()
        
        if not self.reason:
            raise UserError(_('Debe especificar un motivo para la reversión.'))
        
        if self.reverse_partial and not self.reverse_amount:
            raise UserError(_('Debe especificar el monto a revertir para reversión parcial.'))

        self.link_id._advance_check_cancel_allowed(self.link_id, _('revertir'))

        # Registrar motivo en chatter antes de revertir
        self.link_id.payment_id.message_post(
            body=_('Reversión de aplicación: %s\nMotivo: %s', 
                   self.link_id.display_name, self.reason)
        )
        
        self.link_id.move_id.message_post(
            body=_('Reversión de Abono/Anticipo aplicado: %s\nMotivo: %s',
                   self.link_id.payment_id.name, self.reason)
        )
        
        # Ejecutar reversión
        if self.reverse_partial:
            # TODO: Implementar reversión parcial
            raise UserError(_('La reversión parcial aún no está implementada.'))
        else:
            self.link_id._reverse_advance_application()
            # Agregar motivo al chatter después de revertir
            self.link_id.payment_id.message_post(
                body=_('Motivo de reversión: %s', self.reason)
            )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Abono/Anticipo'),
            'res_model': 'account.payment',
            'res_id': self.link_id.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
