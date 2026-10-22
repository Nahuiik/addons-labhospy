from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    gn_labhospy_supplier_id = fields.Many2one(
        'gn.labhospy.supplier',
        string='Proveedor (LabHosPy)',
        compute='_compute_gn_labhospy_fields',
        store=False,
        readonly=True,
    )
    gn_labhospy_catalog_code = fields.Char(
        string='Código de Catálogo',
        compute='_compute_gn_labhospy_fields',
        store=False,
        readonly=True,
    )
    gn_labhospy_model = fields.Char(
        string='Modelo',
        compute='_compute_gn_labhospy_fields',
        store=False,
        readonly=True,
    )
    gn_labhospy_is_controlled = fields.Boolean(
        string='Producto Controlado',
        compute='_compute_gn_labhospy_fields',
        store=False,
        readonly=True,
    )
    gn_labhospy_template_is_controlled = fields.Boolean(
        related='product_id.product_tmpl_id.gn_labhospy_is_controlled',
        string='Producto controlado (plantilla)',
        readonly=True,
        store=False,
    )

    @api.depends(
        'sale_line_id',
        'sale_line_id.gn_labhospy_supplier_id',
        'sale_line_id.gn_labhospy_catalog_code',
        'sale_line_id.gn_labhospy_model',
        'sale_line_id.gn_labhospy_is_controlled',
        'product_tmpl_id',
        'product_tmpl_id.gn_labhospy_supplier_id',
        'product_tmpl_id.gn_labhospy_catalog_code',
        'product_tmpl_id.gn_labhospy_model',
        'product_tmpl_id.gn_labhospy_is_controlled',
    )
    def _compute_gn_labhospy_fields(self):
        for move in self:
            supplier = False
            catalog = False
            model = False
            is_controlled = False

            if move.sale_line_id:
                supplier = move.sale_line_id.gn_labhospy_supplier_id
                catalog = move.sale_line_id.gn_labhospy_catalog_code
                model = move.sale_line_id.gn_labhospy_model
                is_controlled = move.sale_line_id.gn_labhospy_is_controlled
            elif move.product_tmpl_id:
                supplier = move.product_tmpl_id.gn_labhospy_supplier_id
                catalog = move.product_tmpl_id.gn_labhospy_catalog_code
                model = move.product_tmpl_id.gn_labhospy_model
                is_controlled = move.product_tmpl_id.gn_labhospy_is_controlled

            move.gn_labhospy_supplier_id = supplier
            move.gn_labhospy_catalog_code = catalog
            move.gn_labhospy_model = model
            move.gn_labhospy_is_controlled = is_controlled
