# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

import base64
from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import format_date
from odoo.tools.image import image_data_uri


class SafeFormatDict(dict):
    """Dict que devuelve '' para claves faltantes (evita KeyError en plantillas)."""

    def __missing__(self, key):
        return ''


class HnVacationDocumentType(models.Model):
    _name = 'hn.vacation.document.type'
    _description = 'Tipo de documento de vacaciones'
    _order = 'sequence, code'

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código técnico', required=True, help='constancia, solicitud, preaviso')
    sequence = fields.Integer('Secuencia', default=10)
    active = fields.Boolean('Activo', default=True)
    report_id = fields.Many2one(
        'ir.actions.report',
        string='Reporte',
        domain=[('model', '=', 'hr.leave')],
        help='Reporte asociado para generar el PDF. Debe ser del modelo Ausencia (hr.leave).',
    )
    header_html = fields.Html(
        'Encabezado',
        sanitize=False,
        help='Contenido del encabezado (logo, título). Usa marcadores como {employee_name}.',
    )
    body_html = fields.Html(
        'Contenido principal',
        sanitize=False,
        help='Cuerpo del documento. Usa los marcadores disponibles.',
    )
    footer_html = fields.Html(
        'Pie de página',
        sanitize=False,
        help='Firma, sello, etc. Usa los mismos marcadores.',
    )
    markers_help_html = fields.Html(
        'Marcadores disponibles',
        compute='_compute_markers_help_html',
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código debe ser único.",
    )

    @api.depends()
    def _compute_markers_help_html(self):
        help_html = '''<div class="mt-2">
        <p class="text-muted">Use estos marcadores entre llaves, ej: <code>{employee_name}</code></p>
        <table class="table table-sm table-bordered">
            <thead><tr><th>Marcador</th><th>Descripción</th></tr></thead>
            <tbody>
                <tr><th colspan="2" class="bg-light">Datos del empleado</th></tr>
                <tr><td><code>{employee_name}</code></td><td>Nombre del empleado</td></tr>
                <tr><td><code>{employee_identification}</code></td><td>Número de identidad</td></tr>
                <tr><td><code>{department_name}</code></td><td>Departamento</td></tr>
                <tr><td><code>{job_name}</code></td><td>Puesto / cargo</td></tr>
                <tr><td><code>{hire_date}</code></td><td>Fecha de ingreso</td></tr>
                <tr><th colspan="2" class="bg-light">Ausencia</th></tr>
                <tr><td><code>{leave_type_name}</code></td><td>Tipo de ausencia (ej. Vacaciones)</td></tr>
                <tr><td><code>{number_of_days}</code></td><td>Días solicitados</td></tr>
                <tr><td><code>{date_from}</code></td><td>Fecha inicio</td></tr>
                <tr><td><code>{date_to}</code></td><td>Fecha fin</td></tr>
                <tr><td><code>{request_date}</code></td><td>Fecha de solicitud</td></tr>
                <tr><th colspan="2" class="bg-light">Aprobaciones</th></tr>
                <tr><td><code>{manager_name}</code></td><td>Jefe inmediato</td></tr>
                <tr><td><code>{first_approver_name}</code></td><td>Primer aprobador</td></tr>
                <tr><td><code>{second_approver_name}</code></td><td>Segundo aprobador (RRHH)</td></tr>
                <tr><th colspan="2" class="bg-light">Empresa</th></tr>
                <tr><td><code>{company_name}</code></td><td>Nombre de la empresa</td></tr>
                <tr><td><code>{company_address}</code></td><td>Dirección</td></tr>
                <tr><td><code>{company_phone}</code></td><td>Teléfono</td></tr>
                <tr><td><code>{company_city}</code></td><td>Ciudad</td></tr>
                <tr><td><code>{company_logo_img}</code></td><td>Logo de la empresa (img HTML)</td></tr>
                <tr><th colspan="2" class="bg-light">Otros</th></tr>
                <tr><td><code>{today}</code></td><td>Fecha de emisión</td></tr>
                <tr><td><code>{signer_name}</code></td><td>Nombre del firmante (constancia)</td></tr>
                <tr><td><code>{signer_id_number}</code></td><td>Identidad del firmante</td></tr>
                <tr><td><code>{sign_date}</code></td><td>Fecha de firma</td></tr>
                <tr><td><code>{signature_img}</code></td><td>Imagen de firma (solo constancia)</td></tr>
            </tbody>
        </table>
        </div>'''
        for rec in self:
            rec.markers_help_html = help_html

    def _get_render_values(self, leave):
        """Valores para sustituir en las plantillas HTML."""
        self.ensure_one()
        leave.ensure_one()
        # PDF/QWeb puede ejecutarse con empresas permitidas distintas a la del registro.
        leave = leave.sudo()
        env = leave.env
        company = leave.company_id or leave.employee_id.company_id or env.company
        emp = leave.employee_id
        report_date = fields.Date.context_today(self)

        hire_date = ''
        if emp:
            start = getattr(emp, 'contract_date_start', None)
            if start:
                hire_date = format_date(env, start)

        request_date = ''
        if leave.create_date:
            request_date = format_date(env, leave.create_date.date())

        date_from = leave.request_date_from and format_date(env, leave.request_date_from) or ''
        date_to = leave.request_date_to and format_date(env, leave.request_date_to) or ''

        sign_date = ''
        if leave.hn_sign_date:
            sign_date = format_date(env, leave.hn_sign_date)

        signature_img = ''
        if leave.hn_signature and self.code == 'constancia':
            raw = leave.hn_signature
            if isinstance(raw, bytes):
                b64 = base64.b64encode(raw).decode('ascii')
            elif isinstance(raw, str) and not raw.startswith('data:'):
                b64 = raw
            else:
                b64 = ''
            if b64:
                signature_img = '<img src="data:image/png;base64,%s" alt="Firma" style="max-height: 80px;"/>' % b64

        # Logo de la empresa (usa image_data_uri de Odoo para compatibilidad)
        company_logo_img = ''
        if company:
            try:
                logo = company.with_context(bin_size=False).logo or (
                    company.partner_id and company.partner_id.with_context(bin_size=False).image_1920
                )
                if logo:
                    # image_data_uri espera bytes en base64; Binary de Odoo devuelve base64
                    if isinstance(logo, str) and not logo.startswith('data:'):
                        logo_b64 = logo.encode('ascii')
                    elif isinstance(logo, bytes):
                        # Si son bytes crudos (imagen), codificar a base64
                        if len(logo) >= 3 and logo[:3] in (b'\xff\xd8\xff', b'\x89PN'):
                            logo_b64 = base64.b64encode(logo)
                        else:
                            logo_b64 = logo  # Ya está en base64
                    else:
                        logo_b64 = None
                    if logo_b64:
                        uri = image_data_uri(logo_b64)
                        alt = (company.name or '').replace('"', '&quot;')
                        company_logo_img = (
                            '<img src="%s" alt="%s" '
                            'style="max-height: 80px; max-width: 180px; object-fit: contain;"/>'
                        ) % (uri, alt)
            except Exception:
                pass

        # Departamento, puesto, tipo de ausencia
        department_name = ''
        if emp and getattr(emp, 'department_id', None) and emp.department_id:
            department_name = emp.department_id.name or ''
        elif getattr(leave, 'department_id', None) and leave.department_id:
            department_name = leave.department_id.name or ''

        job_name = ''
        if emp:
            job_name = (
                getattr(emp, 'job_id', None) and emp.job_id.name or
                getattr(emp, 'job_title', None) or ''
            )

        leave_type_name = ''
        if leave.holiday_status_id:
            leave_type_name = leave.holiday_status_id.name or ''

        # Jefe inmediato y aprobadores
        manager_name = ''
        if emp:
            manager = getattr(emp, 'leave_manager_id', None) or getattr(emp, 'parent_id', None)
            if manager:
                manager_name = manager.name or ''

        first_approver_name = ''
        if getattr(leave, 'first_approver_id', None) and leave.first_approver_id:
            first_approver_name = leave.first_approver_id.name or ''

        second_approver_name = ''
        if getattr(leave, 'second_approver_id', None) and leave.second_approver_id:
            second_approver_name = leave.second_approver_id.name or ''

        # Dirección y teléfono de la empresa
        company_address = ''
        company_phone = ''
        if company:
            parts = []
            if getattr(company, 'street', None):
                parts.append(company.street)
            if getattr(company, 'street2', None):
                parts.append(company.street2)
            if getattr(company, 'city', None):
                parts.append(company.city)
            if getattr(company, 'state_id', None) and company.state_id:
                parts.append(company.state_id.name)
            if getattr(company, 'country_id', None) and company.country_id:
                parts.append(company.country_id.name)
            company_address = ', '.join(p for p in parts if p)
            company_phone = getattr(company, 'phone', None) or ''

        values = SafeFormatDict({
            'employee_name': emp.name or '' if emp else '',
            'employee_identification': emp.identification_id or '' if emp else '',
            'department_name': department_name,
            'job_name': job_name,
            'hire_date': hire_date,
            'leave_type_name': leave_type_name,
            'number_of_days': int(leave.number_of_days) if leave.number_of_days else 0,
            'date_from': date_from,
            'date_to': date_to,
            'request_date': request_date,
            'manager_name': manager_name,
            'first_approver_name': first_approver_name,
            'second_approver_name': second_approver_name,
            'company_name': company.name or '',
            'company_address': company_address,
            'company_phone': company_phone,
            'company_city': company.city or '' if company else '',
            'company_logo_img': company_logo_img,
            'today': format_date(env, report_date),
            'signer_name': leave.hn_signer_name or '',
            'signer_id_number': leave.hn_signer_id_number or '',
            'sign_date': sign_date,
            'signature_img': signature_img,
        })
        return values

    def render_header_html(self, leave):
        """Renderiza el encabezado con los valores del leave."""
        self.ensure_one()
        if not self.header_html:
            return Markup('')
        values = self._get_render_values(leave)
        return Markup((self.header_html or '').format_map(values))

    def render_body_html(self, leave):
        """Renderiza el cuerpo con los valores del leave."""
        self.ensure_one()
        if not self.body_html:
            return Markup('')
        values = self._get_render_values(leave)
        return Markup((self.body_html or '').format_map(values))

    def render_footer_html(self, leave):
        """Renderiza el pie con los valores del leave."""
        self.ensure_one()
        if not self.footer_html:
            return Markup('')
        values = self._get_render_values(leave)
        return Markup((self.footer_html or '').format_map(values))
