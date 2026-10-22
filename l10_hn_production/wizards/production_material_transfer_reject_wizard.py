# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class HnProductionMaterialTransferRejectWizard(models.TransientModel):
    _name = "hn.production.material.transfer.reject.wizard"
    _description = "Rechazar transferencia a producción"

    transfer_id = fields.Many2one(
        "hn.production.material.transfer",
        string="Transferencia",
        required=True,
        readonly=True,
    )
    rejection_reason = fields.Text(
        string="Motivo de rechazo",
        required=True,
    )

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.rejection_reason.strip():
            raise UserError(_("Indique el motivo del rechazo."))
        transfer = self.transfer_id
        transfer._check_approver_access()
        transfer._check_not_self_approval()
        transfer._apply_rejection(self.rejection_reason.strip())
        return {"type": "ir.actions.act_window_close"}
