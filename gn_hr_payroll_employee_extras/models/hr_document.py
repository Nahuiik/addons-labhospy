# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _


class HrDocumentType(models.Model):
    """Catalog of document types for employee entry documents"""
    _name = 'hr.document.type'
    _description = 'Tipo de Documento'
    _order = 'sequence, name'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    is_required = fields.Boolean(string='Obligatorio', default=False,
                                  help='Si está marcado, el documento será requerido para todos los empleados')

    _name_company_uniq = models.Constraint(
        'unique (name, company_id)',
        'El nombre del tipo de documento debe ser único por compañía.'
    )


class HrEmployeeDocument(models.Model):
    """Employee entry documents"""
    _name = 'hr.employee.document'
    _description = 'Documento de Empleado'
    _order = 'document_type_id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )
    document_type_id = fields.Many2one(
        'hr.document.type',
        string='Tipo de Documento',
        required=True,
        check_company=True,
    )
    document = fields.Binary(string='Documento', attachment=True)
    document_filename = fields.Char(string='Nombre del Archivo')
    is_missing = fields.Boolean(
        string='Faltante',
        compute='_compute_is_missing',
        store=True
    )
    is_required = fields.Boolean(
        string='Obligatorio',
        related='document_type_id.is_required',
        store=True
    )
    file_extension = fields.Char(
        string='Extensión',
        compute='_compute_file_extension',
        store=True
    )
    can_preview = fields.Boolean(
        string='Puede Previsualizar',
        compute='_compute_file_extension',
        store=True
    )

    @api.depends('document')
    def _compute_is_missing(self):
        for doc in self:
            doc.is_missing = not doc.document

    @api.depends('document_filename')
    def _compute_file_extension(self):
        preview_extensions = ['pdf', 'jpg', 'jpeg', 'png']
        for doc in self:
            if doc.document_filename:
                ext = doc.document_filename.split('.')[-1].lower() if '.' in doc.document_filename else ''
                doc.file_extension = ext
                doc.can_preview = ext in preview_extensions
            else:
                doc.file_extension = ''
                doc.can_preview = False

    @api.onchange('document', 'document_filename')
    def _onchange_document(self):
        """Validate file extension"""
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
        if self.document_filename:
            ext = self.document_filename.split('.')[-1].lower() if '.' in self.document_filename else ''
            if ext and ext not in allowed_extensions:
                return {
                    'warning': {
                        'title': _('Formato no permitido'),
                        'message': _('Solo se permiten archivos PDF, JPG, PNG o Word (doc, docx). '
                                    'El archivo "%s" no será guardado.') % self.document_filename
                    }
                }

    @api.constrains('document', 'document_filename')
    def _check_file_extension(self):
        """Validate file extension on save"""
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
        for doc in self:
            if doc.document and doc.document_filename:
                ext = doc.document_filename.split('.')[-1].lower() if '.' in doc.document_filename else ''
                if ext and ext not in allowed_extensions:
                    raise models.ValidationError(
                        _('Solo se permiten archivos PDF, JPG, PNG o Word (doc, docx). '
                          'El archivo "%s" tiene un formato no permitido.') % doc.document_filename
                    )

    def action_preview_document(self):
        """Open document preview in a popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vista Previa del Documento'),
            'res_model': 'hr.employee.document',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
