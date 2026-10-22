# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        # El formulario crea el borrador vacío; la validación estricta aplica en writes posteriores
        # (y en create si el payload ya viene completo).
        return super(
            AccountMove,
            self.with_context(_gn_vendor_bill_allow_incomplete_create=True),
        ).create(vals_list)

    @staticmethod
    def _gn_vendor_bill_meaningful_lines(move):
        skip_types = (
            'line_section',
            'line_subsection',
            'line_note',
            'payment_term',
        )
        return move.invoice_line_ids.filtered(
            lambda l: l.display_type not in skip_types
        )

    @api.constrains(
        'move_type',
        'state',
        'partner_id',
        'invoice_line_ids',
    )
    def _gn_check_vendor_bill_draft_complete(self):
        """Factura / NC / recibo de proveedor en borrador: siempre exige proveedor y líneas.

        Cualquier guardado en borrador debe tener proveedor y al menos una línea de detalle
        (no cuenta secciones, notas ni líneas solo de plazo de pago).
        """
        for move in self:
            if move.move_type not in ('in_invoice', 'in_refund', 'in_receipt'):
                continue
            if move.state != 'draft':
                continue
            lines_ok = bool(self._gn_vendor_bill_meaningful_lines(move))
            if self.env.context.get('_gn_vendor_bill_allow_incomplete_create'):
                if not (move.partner_id and lines_ok):
                    continue
            if not move.partner_id:
                raise ValidationError(
                    _('Debe indicar el proveedor antes de guardar la factura de proveedor.')
                )
            if not self._gn_vendor_bill_meaningful_lines(move):
                raise ValidationError(
                    _('Debe agregar al menos una línea en la factura antes de guardar.')
                )
