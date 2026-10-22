# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class GnHrAttendanceCorrectionRequest(models.Model):
    _name = 'gn.hr.attendance.correction.request'
    _description = 'Solicitud de corrección de asistencia'
    _order = 'request_date desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True,
    )
    attendance_id = fields.Many2one(
        'hr.attendance',
        string='Registro de asistencia',
        required=True,
        ondelete='cascade',
        domain="[('employee_id', '=', employee_id)]",
    )
    request_date = fields.Datetime(
        string='Fecha solicitud',
        default=fields.Datetime.now,
        readonly=True,
    )
    current_check_in = fields.Datetime(
        related='attendance_id.check_in',
        string='Entrada actual',
        readonly=True,
    )
    current_check_out = fields.Datetime(
        related='attendance_id.check_out',
        string='Salida actual',
        readonly=True,
    )
    requested_check_in = fields.Datetime(
        string='Entrada solicitada',
        required=True,
    )
    requested_check_out = fields.Datetime(
        string='Salida solicitada',
    )
    reason = fields.Text(
        string='Motivo',
        required=True,
    )
    state = fields.Selection(
        [
            ('submitted', 'Enviada'),
            ('approved', 'Aprobada'),
            ('rejected', 'Rechazada'),
        ],
        string='Estado',
        default='submitted',
        required=True,
        readonly=True,
    )
    approver_id = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
    )
    approved_on = fields.Datetime(
        string='Fecha aprobación',
        readonly=True,
    )
    rejection_reason = fields.Text(
        string='Motivo de rechazo',
        readonly=True,
    )

    @api.onchange('attendance_id')
    def _onchange_attendance_id(self):
        if self.attendance_id:
            self.requested_check_in = self.attendance_id.check_in
            self.requested_check_out = self.attendance_id.check_out

    def action_approve(self):
        self.ensure_one()
        if self.state != 'submitted':
            return
        self.attendance_id.sudo().write({
            'check_in': self.requested_check_in,
            'check_out': self.requested_check_out or False,
        })
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approved_on': fields.Datetime.now(),
        })

    def action_reject(self):
        self.ensure_one()
        if self.state != 'submitted':
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rechazar solicitud'),
            'res_model': 'gn.hr.attendance.correction.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def _action_reject_with_reason(self, reason):
        self.ensure_one()
        self.write({
            'state': 'rejected',
            'approver_id': self.env.user.id,
            'approved_on': fields.Datetime.now(),
            'rejection_reason': reason,
        })
