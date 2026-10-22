from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    gn_labhospy_sanitary_license_no = fields.Char(
        string='No. licencia sanitaria (SC) por defecto',
        help='Número de licencia sanitaria por defecto para las sucursales.',
    )
    gn_labhospy_sanitary_license_document = fields.Binary(
        string='Documento de licencia (SC)',
        attachment=True,
        help='Archivo de la licencia sanitaria de la sucursal.',
    )
    gn_labhospy_sanitary_license_document_filename = fields.Char(
        string='Nombre archivo licencia',
    )

class ResBranch(models.Model):
    _inherit = 'res.branch'

    gn_labhospy_sanitary_license_no = fields.Char(
        string='No. licencia sanitaria (SC)',
        help='Número de licencia sanitaria de la sucursal para el informe de sustancias controladas.',
    )
    gn_labhospy_sanitary_license_document = fields.Binary(
        string='Documento de licencia (SC)',
        attachment=True,
        help='Archivo de la licencia sanitaria de la sucursal.',
    )
    gn_labhospy_sanitary_license_document_filename = fields.Char(
        string='Nombre archivo licencia',
    )
