# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import email_normalize

from odoo.addons.auth_signup.models.res_partner import SignupError
from odoo.addons.base.models.ir_mail_server import MailDeliveryException

_logger = logging.getLogger(__name__)


class GnHrEmployeePortalInviteWizard(models.TransientModel):
    _name = 'gn.hr.employee.portal.invite.wizard'
    _description = 'Invitar empleado al portal'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    send_email = fields.Boolean(
        string='Enviar invitación por correo',
        default=True,
        help='Si está marcado, se envía el correo con la plantilla de portal de Odoo. '
             'El enlace también queda disponible abajo por si el correo no llega.',
    )
    invitation_link = fields.Char(string='Enlace para compartir', readonly=True)
    info_message = fields.Text(string='Detalle', readonly=True)

    def _action_open_modal(self):
        self.ensure_one()
        return {
            'name': _('Invitar al portal del empleado'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _send_portal_mail(self, user):
        template = self.env.ref('auth_signup.portal_set_password_email', raise_if_not_found=False)
        if not template:
            raise UserError(_('No se encontró la plantilla de correo "Portal: nuevo usuario" (auth_signup).'))
        user = user.sudo()
        template.with_context(
            dbname=self.env.cr.dbname,
            lang=user.lang or self.env.lang,
            welcome_message='',
            medium='portalinvite',
        ).send_mail_payroll_tracked(user.id, force_send=True)

    def _compute_invitation_url(self, partner):
        partner = partner.sudo()
        if not partner.signup_type:
            partner.signup_prepare()
        return partner._get_signup_url_for_action().get(partner.id) or ''

    def action_send_invitation(self):
        self.ensure_one()
        employee = self.employee_id.sudo()
        group_portal = self.env.ref('base.group_portal')
        group_public = self.env.ref('base.group_public')
        group_employee_portal = self.env.ref('gn_hn_hr_employee_portal.group_employee_portal_user')

        if not employee.work_email or not email_normalize(employee.work_email):
            raise UserError(_('Defina un correo laboral válido para el empleado.'))
        email_norm = email_normalize(employee.work_email)

        if not employee.work_contact_id:
            employee._create_work_contacts()

        partner = employee.work_contact_id.sudo()
        partner.write({'email': email_norm})

        if employee.user_id:
            user = employee.user_id.sudo()
            if user._is_internal():
                raise UserError(_(
                    'Este empleado ya tiene un usuario interno (%s). '
                    'No se puede usar la invitación automática al portal.',
                ) % user.login)
            if not user._is_portal():
                raise UserError(_(
                    'El usuario vinculado no es de tipo portal. Revise el usuario %s.',
                ) % user.login)
            if group_employee_portal not in user.group_ids:
                user.write({'group_ids': [(4, group_employee_portal.id)]})
            user.partner_id.signup_prepare()
            mail_error = None
            if self.send_email:
                try:
                    self._send_portal_mail(user)
                except MailDeliveryException as e:
                    mail_error = str(e)
                    _logger.warning('Fallo al enviar invitación portal: %s', e)
            invitation_url = self._compute_invitation_url(user.partner_id)
            self.invitation_link = invitation_url
            self.info_message = _(
                'Se renovó el enlace de acceso. '
                'El empleado ya tenía usuario portal vinculado.'
            )
            if mail_error:
                self.info_message += '\n\n' + (
                    _('Advertencia: no se pudo enviar el correo. Comparta el enlace manualmente.') + ' ' + mail_error
                )
            return self._action_open_modal()

        existing = self.env['res.users'].with_context(active_test=False).sudo().search([
            ('login', '=', email_norm),
        ], limit=1)
        linked_existing_login = bool(existing)
        if existing:
            if existing.partner_id.id != partner.id:
                raise UserError(_(
                    'Ya existe otro usuario con el correo %s. Use otro correo o vincule ese usuario manualmente.',
                ) % email_norm)
            user = existing
            if user._is_internal():
                raise UserError(_(
                    'Ya existe un usuario interno con el correo %s. No se puede usar para el portal del empleado.',
                ) % email_norm)
            user.write({
                'active': True,
                'group_ids': [
                    (4, group_portal.id),
                    (3, group_public.id),
                    (4, group_employee_portal.id),
                ],
            })
            employee.user_id = user
        else:
            try:
                user = self.env['res.users'].with_context(no_reset_password=True).sudo()._create_user_from_template({
                    'email': email_norm,
                    'login': email_norm,
                    'partner_id': partner.id,
                    'company_id': employee.company_id.id,
                    'company_ids': [(6, 0, employee.company_id.ids)],
                })
            except SignupError as e:
                raise UserError(str(e)) from e

            user.write({
                'group_ids': [
                    (4, group_portal.id),
                    (3, group_public.id),
                    (4, group_employee_portal.id),
                ],
                'active': True,
            })
            employee.user_id = user

        user.partner_id.signup_prepare()
        mail_error = None
        if self.send_email:
            try:
                self._send_portal_mail(user)
            except MailDeliveryException as e:
                mail_error = str(e)
                _logger.warning('Fallo al enviar invitación portal: %s', e)

        invitation_url = self._compute_invitation_url(user.partner_id)
        self.invitation_link = invitation_url
        if linked_existing_login:
            self.info_message = _(
                'Se vinculó al empleado un usuario portal que ya existía con ese correo. '
                'Comparta el enlace si hace falta.'
            )
        else:
            self.info_message = _(
                'Usuario portal creado y vinculado al empleado. '
                'Comparta el enlace si el correo no llega o el empleado no lo encuentra.'
            )
        if mail_error:
            self.info_message += '\n\n' + (
                _('Advertencia: no se pudo enviar el correo. Use el enlace de abajo.') + ' ' + mail_error
            )
        return self._action_open_modal()
