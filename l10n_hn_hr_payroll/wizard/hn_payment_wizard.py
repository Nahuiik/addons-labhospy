# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HnPaymentWizard(models.TransientModel):
    _name = 'hn.payment.wizard'
    _description = 'Registrar pago anticipado de vacaciones'

    leave_id = fields.Many2one(
        'hr.leave',
        string='Solicitud de vacaciones',
        required=True,
        readonly=True,
    )
    paid_date = fields.Date(
        string='Fecha de pago',
        required=True,
        default=fields.Date.context_today,
    )
    paid_amount = fields.Float(
        string='Monto pagado',
    )
    payment_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Comprobante de pago',
    )
    register_in_payroll = fields.Boolean(
        string='Registrar en nómina',
        default=False,
        help='Crear entrada de vacaciones en nómina (motor CE l10n_hn_payroll_base)',
    )
    has_hr_payroll = fields.Boolean(compute='_compute_has_hr_payroll')

    @api.depends()
    def _compute_has_hr_payroll(self):
        installed = bool(
            self.env['ir.module.module'].sudo().search([
                ('name', '=', 'l10n_hn_payroll_base'),
                ('state', '=', 'installed'),
            ])
        )
        for w in self:
            w.has_hr_payroll = installed

    @api.model
    def _hr_payroll_installed(self):
        return bool(
            self.env['ir.module.module'].sudo().search([
                ('name', '=', 'l10n_hn_payroll_base'),
                ('state', '=', 'installed'),
            ])
        )

    def _get_or_create_vacation_input_type(self):
        """Obtiene o crea el tipo de entrada VACACIONES para nómina."""
        InputType = self.env['hr.payslip.input.type']
        existing = InputType.search([('code', '=', 'VACACIONES')], limit=1)
        if existing:
            return existing
        return InputType.create({
            'name': 'Vacaciones',
            'code': 'VACACIONES',
        })

    def _create_payslip_with_vacation_input(self):
        """Crea nómina con entrada VACACIONES (requiere motor CE de nómina)."""
        self.ensure_one()
        if not self._hr_payroll_installed():
            return None
        leave = self.leave_id
        emp = leave.employee_id
        if not emp:
            return None
        paid = self.paid_date or date.today()
        date_from = paid.replace(day=1)
        date_to = date_from + relativedelta(months=1, days=-1)
        version = emp._get_version(date_from) if hasattr(emp, '_get_version') else emp.version_id
        if not version:
            return None
        struct = version.structure_type_id.default_struct_id if hasattr(version, 'structure_type_id') else None
        if not struct:
            return None
        input_type = self._get_or_create_vacation_input_type()
        if input_type.id not in struct.input_line_type_ids.ids:
            struct.write({'input_line_type_ids': [(4, input_type.id)]})
        payslip_vals = {
            'employee_id': emp.id,
            'version_id': version.id,
            'date_from': date_from,
            'date_to': date_to,
        }
        payslip = self.env['hr.payslip'].create(payslip_vals)
        self.env['hr.payslip.input'].create({
            'payslip_id': payslip.id,
            'input_type_id': input_type.id,
            'amount': self.paid_amount or 0,
            'name': f'Vacaciones - {leave.request_date_from} a {leave.request_date_to}',
        })
        return payslip

    def action_confirm(self):
        self.ensure_one()
        self.leave_id.write({
            'hn_paid_in_advance': True,
            'hn_paid_date': self.paid_date,
            'hn_paid_amount': self.paid_amount,
            'hn_payment_attachment_id': self.payment_attachment_id.id,
        })
        if self.register_in_payroll:
            payslip = self._create_payslip_with_vacation_input()
            if payslip:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Nómina creada',
                    'res_model': 'hr.payslip',
                    'res_id': payslip.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        return {'type': 'ir.actions.act_window_close'}
