# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def button_draft(self):
        """Sobrescribir button_draft para permitir desconciliar recibos de venta"""
        # Para asientos de tipo 'entry' (recibos de venta), desconciliar antes de validar
        # Esto evita el error del módulo gn_cancel_entrys cuando payment_state == 'paid'
        for move in self:
            if move.move_type == 'entry' and move.ref and 'REC' in (move.ref or ''):
                # Desconciliar TODAS las líneas que tengan reconciliaciones
                # Esto es crítico para que payment_state no sea 'paid' cuando gn_cancel_entrys valide
                all_lines = move.line_ids
                if all_lines:
                    # Buscar todas las líneas con cualquier tipo de reconciliación
                    lines_to_unreconcile = all_lines.filtered(
                        lambda l: l.reconciled 
                        or l.matched_debit_ids 
                        or l.matched_credit_ids
                        or l.full_reconcile_id
                    )
                    if lines_to_unreconcile:
                        lines_to_unreconcile.remove_move_reconcile()
                        # Forzar refresh completo del payment_state
                        move.invalidate_recordset(['payment_state'])
                        self.env.flush_all()
                        # Recalcular payment_state
                        move._compute_payment_state()
                        # Verificar una vez más después del flush
                        if move.payment_state == 'paid':
                            move.invalidate_recordset(['payment_state'])
                            move._compute_payment_state()
        
        # Llamar al método padre (que incluye la validación de gn_cancel_entrys)
        return super().button_draft()


