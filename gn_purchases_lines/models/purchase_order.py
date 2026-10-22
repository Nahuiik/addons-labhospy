# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_import_lines(self):
        """Abre el wizard para importar líneas de compra"""
        self.ensure_one()
        return {
            'name': 'Importar Líneas de Compra',
            'type': 'ir.actions.act_window',
            'res_model': 'gn_purchases_lines.import_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_order_id': self.id,
            },
        }

    def action_clear_imported_lines(self):
        """Elimina las líneas importadas en órdenes de compra editables."""
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(
                _(
                    'Solo se pueden limpiar líneas importadas en solicitudes de '
                    'cotización en borrador o enviadas.'
                )
            )

        imported_lines = self.order_line.filtered('is_imported_line')
        if not imported_lines:
            raise UserError(_('No hay líneas importadas para limpiar.'))

        imported_lines.unlink()
        return True











