# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import AccessError

from .portal_employee_mixin import get_employee_from_user


class SalaryAdvance(models.Model):
    _inherit = 'salary.advance'

    @api.model
    def _gn_portal_user_acting(self):
        return (
            bool(self.env.user.share)
            and self.env.user.has_group('gn_hn_hr_employee_portal.group_employee_portal_user')
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self._gn_portal_user_acting():
            employee = get_employee_from_user(self.env, self.env.user)
            if not employee:
                raise AccessError(_('No hay empleado vinculado a su usuario de portal.'))
            company = employee.company_id
            for vals in vals_list:
                vals['employee_id'] = employee.id
                vals['company_id'] = company.id
        return super().create(vals_list)

    def write(self, vals):
        if self._gn_portal_user_acting():
            allowed_keys = {'advance_amount', 'advance_target', 'date', 'notes', 'state'}
            if not set(vals).issubset(allowed_keys):
                raise AccessError(_('No tiene permiso para modificar esos datos del anticipo.'))
            locked = {'approved', 'cancel', 'reject'}
            for rec in self:
                if rec.state in locked:
                    raise AccessError(_('No puede modificar un anticipo en estado «%s».') % rec.state)
                if rec.state != 'draft':
                    if set(vals.keys()) - {'notes'}:
                        raise AccessError(
                            _('Solo puede actualizar las notas mientras RRHH procesa la solicitud.')
                        )
                elif 'state' in vals and vals['state'] != 'submit':
                    raise AccessError(_('Solo puede enviar la solicitud para aprobación.'))
        return super().write(vals)
