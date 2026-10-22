# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

import base64
from odoo import api, fields, models


class HnConstanciaWizard(models.TransientModel):
    _name = 'hn.constancia.wizard'
    _description = 'Registrar constancia firmada'

    leave_id = fields.Many2one(
        'hr.leave',
        string='Solicitud de vacaciones',
        required=True,
        readonly=True,
    )
    sign_date = fields.Date('Fecha de firma', required=True, default=fields.Date.context_today)
    signer_name = fields.Char('Nombre del firmante', required=True)
    signer_id_number = fields.Char('No. identidad del firmante')
    signature = fields.Binary('Firma', attachment=False)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        leave_id = vals.get('leave_id') or self.env.context.get('default_leave_id')
        if leave_id:
            leave = self.env['hr.leave'].browse(leave_id)
            if leave.employee_id:
                if 'signer_name' in fields_list and not vals.get('signer_name'):
                    vals['signer_name'] = leave.employee_id.name or ''
                if 'signer_id_number' in fields_list and not vals.get('signer_id_number'):
                    vals['signer_id_number'] = leave.employee_id.identification_id or ''
        return vals

    def action_confirm(self):
        self.ensure_one()
        leave = self.leave_id
        # Guardar datos de firma en el leave
        leave.write({
            'hn_constancia_signed': True,
            'hn_sign_date': self.sign_date,
            'hn_signer_name': self.signer_name,
            'hn_signer_id_number': self.signer_id_number,
            'hn_signature': self.signature,
        })
        # Generar PDF y adjuntar
        report = self.env.ref('l10n_hn_hr_payroll.action_report_hn_vacation_constancia')
        rendered = self.env['ir.actions.report']._render_qweb_pdf(
            report.report_name, res_ids=[leave.id]
        )
        pdf_content = rendered[0]
        if pdf_content:
            fname = f'Constancia_Vacaciones_{leave.employee_id.name or "empleado"}_{leave.id}.pdf'
            attachment = self.env['ir.attachment'].create({
                'name': fname,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'hr.leave',
                'res_id': leave.id,
                'mimetype': 'application/pdf',
            })
            leave.hn_constancia_attachment_id = attachment
        return {'type': 'ir.actions.act_window_close'}
