from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    show_button_draft = fields.Boolean(string='Show Button Draft', compute='_compute_show_button_draft')

    @api.depends_context('uid')
    def _compute_show_button_draft(self):
        has_cancel_rights = self.env.user.has_group('gn_cancel_entrys.group_cancel_entries_manager')
        for move in self:
            move.show_button_draft = has_cancel_rights

    def button_draft(self):
        # Solo bloquear facturas con pago confirmado; los asientos de pago (entry) pueden pasar a borrador
        invoice_moves = self.filtered(lambda m: m.is_invoice(include_receipts=True))
        if any(m.payment_state == 'paid' for m in invoice_moves):
            raise UserError(_('An invoice that has a confirmed payment cannot be changed to a draft, please unreconcile the payment first'))
        return super().button_draft()
