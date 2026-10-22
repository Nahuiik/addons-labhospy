# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HnReintegroWizard(models.TransientModel):
    _name = 'hn.reintegro.wizard'
    _description = 'Reintegro por urgencia - dividir vacaciones'

    leave_id = fields.Many2one(
        'hr.leave',
        string='Solicitud de vacaciones',
        required=True,
        readonly=True,
        domain="[('gn_vacation_is_primary', '=', True), ('state', '=', 'validate')]",
    )
    reintegro_date = fields.Date(
        string='Fecha de reintegro',
        required=True,
        default=fields.Date.context_today,
        help='Fecha en que el empleado regresa por urgencia',
    )
    reintegro_reason = fields.Text(
        string='Motivo del reintegro',
        required=True,
    )
    reanudacion_date = fields.Date(
        string='Fecha prevista de reanudación',
        required=True,
        help='Fecha desde la cual el empleado tomará los días restantes',
    )
    gastos_extraordinarios = fields.Float(
        string='Gastos extraordinarios',
        help='Monto de gastos por el reintegro (viajes, etc.)',
    )
    gastos_comprobante = fields.Binary(
        string='Comprobante de gastos',
        attachment=True,
    )

    @api.constrains('reintegro_date', 'reanudacion_date')
    def _check_dates(self):
        for w in self:
            if w.leave_id and w.reintegro_date:
                if w.reintegro_date <= w.leave_id.request_date_from:
                    raise UserError(_('La fecha de reintegro debe ser posterior al inicio de las vacaciones.'))
                if w.reintegro_date > w.leave_id.request_date_to + timedelta(days=1):
                    raise UserError(_('La fecha de reintegro no puede ser posterior al día siguiente al fin de las vacaciones.'))
            if w.reanudacion_date and w.reintegro_date and w.reanudacion_date <= w.reintegro_date:
                raise UserError(_('La fecha de reanudación debe ser posterior a la fecha de reintegro.'))

    def action_confirm(self):
        self.ensure_one()
        leave = self.leave_id
        if leave.state != 'validate':
            raise UserError(_('Solo se puede procesar reintegro en vacaciones aprobadas.'))
        today = fields.Date.context_today(self)
        if leave.request_date_from > today or leave.request_date_to < today:
            raise UserError(_('El reintegro aplica solo a vacaciones actualmente en curso.'))
        # Días ya gozados: último día de vacaciones = reintegro_date - 1
        date_from = leave.request_date_from
        reintegro = self.reintegro_date
        last_vacation_day = reintegro - timedelta(days=1)
        days_taken = (last_vacation_day - date_from).days + 1
        total_days = leave.number_of_days
        days_remaining = total_days - days_taken
        if days_remaining <= 0:
            raise UserError(_('No hay días restantes para crear leave pendiente.'))
        # 1. Modificar leave original: date_to = reintegro_date - 1 día
        new_date_to = reintegro - timedelta(days=1)
        leave.write({
            'request_date_to': new_date_to,
            'number_of_days': days_taken,
        })
        # 2. Crear nuevo leave en draft para días restantes
        date_from_new = self.reanudacion_date
        date_to_new = date_from_new + timedelta(days=int(days_remaining) - 1)
        new_leave = self.env['hr.leave'].create({
            'name': f'Vacaciones pendientes (reintegro) - {leave.employee_id.name}',
            'employee_id': leave.employee_id.id,
            'holiday_status_id': leave.holiday_status_id.id,
            'request_date_from': date_from_new,
            'request_date_to': date_to_new,
            'number_of_days': days_remaining,
            'state': 'draft',
        })
        # 3. Registrar en chatter del leave original
        msg = f"<p><b>Reintegro por urgencia</b></p><p>Fecha de reintegro: {reintegro}</p><p>Último día de vacaciones: {new_date_to}</p><p>Motivo: {self.reintegro_reason or '-'}</p>"
        if self.gastos_extraordinarios:
            msg += f"<p>Gastos extraordinarios: {self.gastos_extraordinarios}</p>"
        try:
            msg += f"<p>Días restantes ({days_remaining}) programados en solicitud: {new_leave._get_html_link()}</p>"
        except Exception:
            msg += f"<p>Días restantes ({days_remaining}) - Nueva solicitud: {new_leave.display_name}</p>"
        leave.message_post(body=msg)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vacaciones pendientes',
            'res_model': 'hr.leave',
            'res_id': new_leave.id,
            'view_mode': 'form',
            'target': 'current',
        }
