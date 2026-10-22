from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    gn_labhospy_supplier_id = fields.Many2one(
        related='move_id.gn_labhospy_supplier_id',
        string='Proveedor (LabHosPy)',
        readonly=True,
        store=False,
    )
    gn_labhospy_catalog_code = fields.Char(
        related='move_id.gn_labhospy_catalog_code',
        string='Código de Catálogo',
        readonly=True,
        store=False,
    )
    gn_labhospy_model = fields.Char(
        related='move_id.gn_labhospy_model',
        string='Modelo',
        readonly=True,
        store=False,
    )
    gn_labhospy_is_controlled = fields.Boolean(
        related='move_id.gn_labhospy_is_controlled',
        string='Producto Controlado',
        readonly=True,
        store=False,
    )
    gn_labhospy_product_is_controlled = fields.Boolean(
        related='product_id.product_tmpl_id.gn_labhospy_is_controlled',
        string='Producto controlado (plantilla)',
        readonly=True,
        store=False,
    )
    gn_labhospy_arsa_resolution_no = fields.Char(
        string='No. de resolución de ARSA',
        help='Solo aplica a productos marcados como controlados en la ficha del producto.',
    )
