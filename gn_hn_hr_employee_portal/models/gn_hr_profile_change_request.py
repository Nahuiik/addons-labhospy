# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GnHrProfileChangeRequest(models.Model):
    _name = 'gn.hr.profile.change.request'
    _description = 'Solicitud de cambio de perfil del empleado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'requested_on desc'

    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        tracking=True,
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Solicitado por',
        default=lambda self: self.env.user,
        tracking=True,
    )
    requested_on = fields.Datetime(
        string='Fecha de solicitud',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    # Campos editables en la solicitud
    phone_personal = fields.Char(string='Teléfono personal', tracking=True)
    mobile_phone = fields.Char(string='Mobile', tracking=True)
    address = fields.Text(string='Dirección', tracking=True)
    emergency_contact = fields.Char(string='Contacto de emergencia', tracking=True)
    emergency_contact_phone = fields.Char(string='Teléfono emergencia', tracking=True)
    # Estado
    state = fields.Selection(
        [
            ('submitted', 'Enviada'),
            ('approved', 'Aprobada'),
            ('rejected', 'Rechazada'),
        ],
        string='Estado',
        default='submitted',
        required=True,
        tracking=True,
    )
    approver_id = fields.Many2one('res.users', string='Aprobado por', tracking=True)
    approved_on = fields.Datetime(string='Fecha de aprobación', tracking=True)
    rejection_reason = fields.Text(string='Motivo de rechazo', tracking=True)

    @api.depends('employee_id', 'requested_on')
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.requested_on:
                date_str = rec.requested_on.strftime('%d/%m/%Y %H:%M') if rec.requested_on else ''
                rec.name = _('Solicitud %s - %s') % (rec.employee_id.name, date_str)
            else:
                rec.name = _('Solicitud de cambio de perfil')

    def action_approve(self):
        """Aplica los cambios al empleado y marca como aprobada."""
        for rec in self:
            if rec.state != 'submitted':
                raise ValidationError(_('Solo se pueden aprobar solicitudes en estado Enviada.'))
            vals = {}
            if rec.phone_personal is not False:
                vals['work_phone'] = rec.phone_personal
            if rec.mobile_phone is not False:
                vals['mobile_phone'] = rec.mobile_phone
            if rec.address is not False and rec.employee_id.work_contact_id:
                rec.employee_id.work_contact_id.sudo().write({
                    'street': rec.address or '',
                })
            if rec.emergency_contact is not False and hasattr(rec.employee_id, 'emergency_contact'):
                vals['emergency_contact'] = rec.emergency_contact
            if rec.emergency_contact_phone is not False and hasattr(rec.employee_id, 'emergency_contact_phone'):
                vals['emergency_contact_phone'] = rec.emergency_contact_phone
            if vals:
                rec.employee_id.sudo().write(vals)
            rec.write({
                'state': 'approved',
                'approver_id': self.env.user.id,
                'approved_on': fields.Datetime.now(),
            })
            self.env['gn.hr.portal.audit.log'].sudo().log_action(
                'profile_change_approved',
                model=self._name,
                res_id=rec.id,
                employee_id=rec.employee_id.id,
            )
        return True

    def action_reject(self):
        """Marca la solicitud como rechazada. El motivo se debe ingresar en rejection_reason antes."""
        for rec in self:
            if rec.state != 'submitted':
                raise ValidationError(_('Solo se pueden rechazar solicitudes en estado Enviada.'))
            rec.write({
                'state': 'rejected',
                'approver_id': self.env.user.id,
                'approved_on': fields.Datetime.now(),
            })
        return True
