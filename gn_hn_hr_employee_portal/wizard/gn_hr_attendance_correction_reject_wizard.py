# -*- coding: utf-8 -*-
from odoo import fields, models, _


class GnHrAttendanceCorrectionRejectWizard(models.TransientModel):
    _name = 'gn.hr.attendance.correction.reject.wizard'
    _description = 'Rechazar solicitud de corrección'

    request_id = fields.Many2one(
        'gn.hr.attendance.correction.request',
        string='Solicitud',
        required=True,
        ondelete='cascade',
    )
    rejection_reason = fields.Text(
        string='Motivo de rechazo',
        required=True,
    )

    def action_reject(self):
        self.ensure_one()
        self.request_id._action_reject_with_reason(self.rejection_reason)
        return {'type': 'ir.actions.act_window_close'}
