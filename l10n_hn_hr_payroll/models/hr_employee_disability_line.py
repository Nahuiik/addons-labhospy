# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployeeDisabilityLine(models.Model):
    """Detalle de discapacidad declarada (documento, tipo, fecha)."""
    _name = 'hr.employee.disability.line'
    _description = 'Discapacidad del empleado'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Secuencia', default=10)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True,
    )
    disability_type_id = fields.Many2one(
        'hr.disability.type',
        string='Tipo de discapacidad',
        required=True,
        ondelete='restrict',
    )
    disability_date = fields.Date(string='Fecha', required=True)
    document = fields.Binary(string='Documento', attachment=True)
    document_filename = fields.Char(string='Nombre del archivo')

    _ALLOWED_EXTENSIONS = ('pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx')

    @api.onchange('document', 'document_filename')
    def _onchange_document(self):
        if not self.document_filename:
            return
        ext = (
            self.document_filename.split('.')[-1].lower()
            if '.' in self.document_filename
            else ''
        )
        if ext and ext not in self._ALLOWED_EXTENSIONS:
            return {
                'warning': {
                    'title': _('Formato no permitido'),
                    'message': _(
                        'Solo se permiten archivos PDF, imágenes (JPG, PNG) o Word (doc, docx). '
                        'El archivo "%s" no será guardado.'
                    )
                    % self.document_filename,
                }
            }

    @api.constrains('document', 'document_filename')
    def _check_file_extension(self):
        for line in self:
            if not line.document or not line.document_filename:
                continue
            ext = (
                line.document_filename.split('.')[-1].lower()
                if '.' in line.document_filename
                else ''
            )
            if ext and ext not in self._ALLOWED_EXTENSIONS:
                raise ValidationError(
                    _(
                        'Solo se permiten archivos PDF, imágenes (JPG, PNG) o Word (doc, docx). '
                        'El archivo "%s" tiene un formato no permitido.'
                    )
                    % line.document_filename
                )
