# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals or 'move_id' in vals:
            self._bank_ui_sync_linked_operations()
        return res

    def _bank_ui_sync_linked_operations(self):
        models_map = [
            ('debit.credit', 'move_id'),
            ('bank.check', 'move_id'),
            ('bank.transfer', 'move_id'),
        ]
        for model_name, field_name in models_map:
            if model_name not in self.env:
                continue
            ops = self.env[model_name].search([(field_name, 'in', self.ids)])
            if ops:
                ops._bank_ui_sync_workflow_state()
