from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    gn_labhospy_supplier_id = fields.Many2one(
        'gn.labhospy.supplier',
        string='Proveedor (LabHosPy)',
        help='Proveedor del catálogo definido en la configuración.'
    )
    gn_labhospy_catalog_code = fields.Char(
        string='Código de Catálogo',
        help='Identificador de catálogo proporcionado por el proveedor.'
    )
    gn_labhospy_model = fields.Char(
        string='Modelo',
        help='Modelo del producto según el proveedor.'
    )
    gn_labhospy_is_controlled = fields.Boolean(
        string='Producto Controlado',
        help='Actívelo si el producto requiere controles adicionales.'
    )
    gn_labhospy_application_use_id = fields.Many2one(
        'gn.labhospy.application.use',
        string='Aplicación / uso',
        help='Valor por defecto en pedidos para productos que requieren informe SC.',
    )
    gn_labhospy_sc_presentation = fields.Char(
        string='Presentación (informe SC)',
        help='Texto de presentación para el informe regulatorio (si está vacío se usa el nombre del producto).',
    )

