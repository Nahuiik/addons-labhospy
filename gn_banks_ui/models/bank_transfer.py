# -*- coding: utf-8 -*-
from odoo import models


class BankTransfer(models.Model):
    _name = 'bank.transfer'
    _inherit = ['bank.transfer', 'bank.operation.workflow.mixin']

    def action_validate(self):
        self._bank_ui_check_approval_before_validate()
        res = super().action_validate()
        self._bank_ui_after_validate()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._bank_ui_after_cancel()
        return res

    def action_set_to_draft(self):
        res = super().action_set_to_draft()
        self._bank_ui_after_set_draft()
        return res
