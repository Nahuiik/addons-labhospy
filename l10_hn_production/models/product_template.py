from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    hn_container_tracking = fields.Boolean(
        string="Frasco / envase con contenido",
        help="El producto se almacena por unidad (frasco, bote, etc.) pero en "
        "producción se consume su contenido (p. ej. gramos).",
    )
    hn_container_content_qty = fields.Float(
        string="Contenido por unidad",
        digits="Product Unit of Measure",
        help="Cantidad de contenido utilizable por cada unidad almacenada "
        "(p. ej. 500 g por frasco).",
    )
    hn_container_content_uom_id = fields.Many2one(
        "uom.uom",
        string="UdM del contenido",
        help="Unidad en la que se consume el contenido en la lista de materiales.",
    )
    hn_is_pack = fields.Boolean(
        string="Producto pack",
        help="Se agrega en la pestaña Pack de la orden de fabricación. "
        "Los materiales de su lista de materiales son lo que se consume, "
        "con el costo de cada uno y el total.",
    )

    @api.constrains(
        "hn_container_tracking",
        "hn_container_content_qty",
        "hn_container_content_uom_id",
    )
    def _check_hn_container_tracking(self):
        for template in self:
            if not template.hn_container_tracking:
                continue
            if template.hn_container_content_qty <= 0:
                raise ValidationError(
                    _(
                        "Indique el contenido por unidad para «%(product)s».",
                        product=template.display_name,
                    )
                )
            if not template.hn_container_content_uom_id:
                raise ValidationError(
                    _(
                        "Indique la unidad de medida del contenido para «%(product)s».",
                        product=template.display_name,
                    )
                )

    @api.constrains("hn_is_pack", "type")
    def _check_hn_is_pack(self):
        for template in self:
            if template.hn_is_pack and template.type != "consu":
                raise ValidationError(
                    _(
                        "Solo un producto almacenable o consumible puede ser un pack («%(product)s»).",
                        product=template.display_name,
                    )
                )


class ProductProduct(models.Model):
    _inherit = "product.product"

    hn_container_tracking = fields.Boolean(
        related="product_tmpl_id.hn_container_tracking",
        readonly=False,
    )
    hn_container_content_qty = fields.Float(
        related="product_tmpl_id.hn_container_content_qty",
        readonly=False,
    )
    hn_container_content_uom_id = fields.Many2one(
        related="product_tmpl_id.hn_container_content_uom_id",
        readonly=False,
    )
    hn_is_pack = fields.Boolean(
        related="product_tmpl_id.hn_is_pack",
        readonly=False,
    )

    def _hn_is_container(self):
        self.ensure_one()
        return bool(
            self.hn_container_tracking
            and self.hn_container_content_qty > 0
            and self.hn_container_content_uom_id
        )
