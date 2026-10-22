from odoo import fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _compute_remaining_due_amount(self):
        for move in self:
            move_sign = -1 if move.is_outbound() else 1
            move.remaining_due_amount = move_sign * (abs(move.amount_total_signed) - abs(move.credit_amount))

    def _compute_credit_amount(self):
        for move in self:
            move.credit_amount = 0.0
            move.credit_amount = abs(move.amount_total_signed) - abs(move.amount_residual_signed)

    remaining_due_amount = fields.Float(compute='_compute_remaining_due_amount', string="Remaining Due Amount")
    credit_amount = fields.Float(compute='_compute_credit_amount', string="Credit Amount")

    def action_check_record(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.id,
            'target': 'current',

        }

