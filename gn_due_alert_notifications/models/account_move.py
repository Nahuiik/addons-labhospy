# -*- coding: utf-8 -*-
from odoo import models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _gn_due_alert_post_chatter(self, body):
        """Publica en chatter solo acciones relevantes del usuario."""
        subtype = self.env.ref('mail.mt_note', raise_if_not_found=False)
        for move in self:
            if not move.exists():
                continue
            move.message_post(
                body=body,
                message_type='notification',
                subtype_id=subtype.id if subtype else False,
            )
