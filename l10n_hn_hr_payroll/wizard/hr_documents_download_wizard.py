# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import base64
import io
import re
import zipfile
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrDocumentsDownloadWizard(models.TransientModel):
    _name = 'hr.documents.download.wizard'
    _description = 'Descargar Documentos de Empleados'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        help='Dejar vacío para incluir todos los departamentos.',
    )
    include_archived = fields.Boolean(
        string='Incluir empleados archivados',
        default=False,
    )
    document_type_id = fields.Many2one(
        'hr.document.type',
        string='Tipo de documento',
        help='Para eliminar: seleccione y use "Eliminar tipo". Para descargar solo este tipo: seleccione y use "Descargar tipo seleccionado".',
    )

    def _get_employees(self):
        domain = [
            ('company_id', '=', self.company_id.id),
            ('document_ids', '!=', False),
        ]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if not self.include_archived:
            domain.append(('active', '=', True))
        return self.env['hr.employee'].search(domain)

    def _get_employees_for_discard(self):
        """Employees matching filter (for discard action - no document_ids filter)."""
        domain = [
            ('company_id', '=', self.company_id.id),
        ]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if not self.include_archived:
            domain.append(('active', '=', True))
        return self.env['hr.employee'].search(domain)

    def _safe_filename(self, name):
        return re.sub(r'[^\w\s\-\.]', '_', (name or '').strip()) or 'documento'

    def _get_doc_filename(self, emp, doc):
        """Nombre: Nombre del empleado - tipo de documento"""
        emp_name = (emp.name or 'empleado').strip()
        tipo_name = (doc.document_type_id.name if doc.document_type_id else 'documento').strip()
        ext = doc.file_extension or ''
        if doc.document_filename and '.' in doc.document_filename:
            ext = doc.document_filename.rsplit('.', 1)[-1].lower()
        ext = ext or 'bin'
        base_name = f'{emp_name} - {tipo_name}'
        return self._safe_filename(base_name) + f'.{ext}'

    def action_download(self):
        employees = self._get_employees()
        if not employees:
            raise UserError(_('No hay empleados con documentos que coincidan con el filtro.'))

        buffer = io.BytesIO()
        files_added = 0
        used_names = set()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for emp in employees:
                docs = emp.document_ids.filtered(lambda d: d.document)
                if not docs:
                    continue
                emp_name = self._safe_filename(emp.name or 'empleado')
                emp_id = emp.identification_id or str(emp.id)
                folder = f'{emp_name}_{emp_id}'
                for doc in docs:
                    filename = self._get_doc_filename(emp, doc)
                    arcname = f'{folder}/{filename}'
                    if arcname in used_names:
                        base, ext = filename.rsplit('.', 1)
                        idx = 1
                        while arcname in used_names:
                            arcname = f'{folder}/{base}_{idx}.{ext}'
                            idx += 1
                    used_names.add(arcname)
                    files_added += 1
                    content = base64.b64decode(doc.document)
                    zf.writestr(arcname, content)

        if files_added == 0:
            raise UserError(_('Ningún empleado tiene documentos con archivos cargados.'))

        buffer.seek(0)
        zip_filename = f'Documentos_Empleados_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        attachment = self.env['ir.attachment'].create({
            'name': zip_filename,
            'type': 'binary',
            'datas': base64.b64encode(buffer.read()),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true&filename={zip_filename}',
            'target': 'self',
        }

    def action_download_document_type(self):
        """Descargar solo el tipo de documento seleccionado de todos los empleados en un ZIP."""
        if not self.document_type_id:
            raise UserError(_('Debe seleccionar un tipo de documento para descargar.'))
        employees = self._get_employees()
        docs = self.env['hr.employee.document'].search([
            ('employee_id', 'in', employees.ids),
            ('document_type_id', '=', self.document_type_id.id),
            ('document', '!=', False),
        ])
        if not docs:
            raise UserError(
                _('No hay documentos del tipo "%s" cargados en los empleados que coinciden con el filtro.')
                % self.document_type_id.name
            )
        buffer = io.BytesIO()
        used_names = set()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for doc in docs:
                filename = self._get_doc_filename(doc.employee_id, doc)
                if filename in used_names:
                    base, ext = filename.rsplit('.', 1)
                    idx = 1
                    while filename in used_names:
                        filename = f'{base}_{idx}.{ext}'
                        idx += 1
                used_names.add(filename)
                content = base64.b64decode(doc.document)
                zf.writestr(filename, content)
        buffer.seek(0)
        tipo_safe = self._safe_filename(self.document_type_id.name)
        zip_filename = f'{tipo_safe}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        attachment = self.env['ir.attachment'].create({
            'name': zip_filename,
            'type': 'binary',
            'datas': base64.b64encode(buffer.read()),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true&filename={zip_filename}',
            'target': 'self',
        }

    def action_discard_document_type(self):
        """Eliminar documentos del tipo seleccionado de todos los empleados que coincidan con el filtro."""
        if not self.document_type_id:
            raise UserError(_('Debe seleccionar un tipo de documento a eliminar.'))
        employees = self._get_employees_for_discard()
        if not employees:
            raise UserError(_('No hay empleados que coincidan con el filtro.'))
        docs = self.env['hr.employee.document'].search([
            ('document_type_id', '=', self.document_type_id.id),
            ('employee_id', 'in', employees.ids),
        ])
        if not docs:
            raise UserError(
                _('No hay documentos del tipo "%s" en los empleados que coinciden con el filtro.')
                % self.document_type_id.name
            )
        count = len(docs)
        docs.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Documentos eliminados'),
                'message': _('Se eliminaron %d documento(s) del tipo "%s".')
                % (count, self.document_type_id.name),
                'type': 'success',
                'sticky': False,
            }
        }
