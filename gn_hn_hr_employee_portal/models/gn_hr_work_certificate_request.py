# -*- coding: utf-8 -*-
import base64
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GnHrWorkCertificateRequest(models.Model):
    _name = 'gn.hr.work.certificate.request'
    _description = 'Solicitud de constancia de trabajo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self: self._default_name(),
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        tracking=True,
    )
    request_date = fields.Datetime(
        string='Fecha de solicitud',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    certificate_type_id = fields.Many2one(
        'hr.work.certificate.type',
        string='Tipo de constancia',
        required=True,
        tracking=True,
        domain="[('for_portal', '=', True), ('company_id', '=', company_id)]",
    )
    recipient_id = fields.Many2one(
        'hr.certificate.recipient',
        string='Dirigido a',
        tracking=True,
    )
    footer_id = fields.Many2one(
        'hr.work.certificate.footer',
        string='Pie de documento',
        tracking=True,
    )
    quality_ids = fields.Many2many(
        'hr.work.certificate.quality',
        relation='gn_cert_request_quality_rel',
        column1='request_id',
        column2='quality_id',
        string='Cualidades',
        help='Cualidades asociadas para constancias de exempleados.',
        tracking=True,
    )
    version_id = fields.Many2one(
        'hr.version',
        string='Contrato relacionado',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    purpose = fields.Char(string='Propósito', tracking=True)
    notes = fields.Text(string='Notas', tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'gn_certificate_request_attachment_rel',
        'request_id',
        'attachment_id',
        string='Adjuntos',
        tracking=True,
    )
    state = fields.Selection(
        [
            ('submitted', 'Enviada'),
            ('in_review', 'En revisión'),
            ('issued', 'Emitida'),
            ('rejected', 'Rechazada'),
            ('cancelled', 'Cancelada'),
        ],
        string='Estado',
        default='submitted',
        required=True,
        tracking=True,
    )
    work_certificate_id = fields.Many2one(
        'hr.work.certificate',
        string='Constancia emitida',
        readonly=True,
        tracking=True,
    )
    issued_document_id = fields.Many2one(
        'ir.attachment',
        string='Documento emitido',
        tracking=True,
    )
    issued_on = fields.Datetime(string='Fecha de emisión', tracking=True)
    issued_by = fields.Many2one('res.users', string='Emitido por', tracking=True)
    rejected_reason = fields.Text(string='Motivo de rechazo', tracking=True)

    def action_in_review(self):
        for rec in self:
            if rec.state != 'submitted':
                raise ValidationError(_('Solo se pueden pasar a revisión solicitudes enviadas.'))
            rec.write({'state': 'in_review'})

    def action_reject(self):
        for rec in self:
            if rec.state not in ('submitted', 'in_review'):
                raise ValidationError(_('No se puede rechazar en el estado actual.'))
            rec.write({'state': 'rejected'})
        return True

    @api.model
    def _default_name(self):
        sequence = self.env['ir.sequence'].next_by_code('gn.hr.work.certificate.request')
        return sequence or _('Nueva solicitud')

    @api.onchange('employee_id')
    def _onchange_employee_version(self):
        """Hereda el contrato vigente del empleado."""
        if self.employee_id:
            if self.employee_id.company_id:
                self.company_id = self.employee_id.company_id
        if self.employee_id and self.employee_id.current_version_id:
            self.version_id = self.employee_id.current_version_id

    @api.onchange('certificate_type_id')
    def _onchange_certificate_type_recipient(self):
        """Carga destinatario y firma por defecto al seleccionar el tipo."""
        if self.certificate_type_id:
            if self.certificate_type_id.no_recipient:
                self.recipient_id = False
            elif self.certificate_type_id.recipient_id:
                self.recipient_id = self.certificate_type_id.recipient_id
            if self.certificate_type_id.default_footer_id:
                self.footer_id = self.certificate_type_id.default_footer_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('employee_id') and not vals.get('company_id'):
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                if employee.company_id:
                    vals['company_id'] = employee.company_id.id
            if vals.get('certificate_type_id') and not vals.get('footer_id'):
                cert_type = self.env['hr.work.certificate.type'].browse(vals['certificate_type_id'])
                if cert_type.default_footer_id:
                    vals['footer_id'] = cert_type.default_footer_id.id
            if vals.get('employee_id') and not vals.get('version_id'):
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                if employee.current_version_id:
                    vals['version_id'] = employee.current_version_id.id
        return super().create(vals_list)

    def action_issue(self):
        """Crea la constancia hr.work.certificate, la valida y genera el PDF."""
        Report = self.env['ir.actions.report']
        Cert = self.env['hr.work.certificate']
        for rec in self:
            if rec.state not in ('submitted', 'in_review'):
                raise ValidationError(_('No se puede emitir en el estado actual.'))
            if not rec.certificate_type_id.no_recipient and not rec.recipient_id:
                raise ValidationError(_(
                    'Debe indicar el destinatario (Dirigido a) para este tipo de constancia.'
                ))
            cert_vals = {
                'employee_id': rec.employee_id.id,
                'certificate_type_id': rec.certificate_type_id.id,
                'recipient_id': rec.recipient_id.id if rec.recipient_id else False,
                'footer_id': rec.footer_id.id if rec.footer_id else False,
                'quality_ids': [(6, 0, rec.quality_ids.ids)],
                'version_id': rec.version_id.id if rec.version_id else False,
                'company_id': rec.company_id.id,
            }
            cert = Cert.with_context(
                skip_certificate_contract_state_validation=True,
            ).create(cert_vals)
            cert.sudo().action_validate()
            report = self.env.ref(
                'gn_hr_documents.action_report_hr_work_certificate',
                raise_if_not_found=False,
            )
            if report:
                pdf_content, _ = Report._render_qweb_pdf(report.id, cert.ids)
                pdf_bytes = pdf_content if isinstance(pdf_content, bytes) else pdf_content.encode()
                attachment = self.env['ir.attachment'].sudo().create({
                    'name': "Constancia_%s.pdf" % (rec.employee_id.name or 'empleado').replace(' ', '_'),
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_bytes),
                    'res_model': self._name,
                    'res_id': rec.id,
                })
            else:
                attachment = self.env['ir.attachment'].browse()
            rec.write({
                'state': 'issued',
                'work_certificate_id': cert.id,
                'issued_document_id': attachment.id if attachment else False,
                'issued_on': fields.Datetime.now(),
                'issued_by': self.env.user.id,
            })
        return True
