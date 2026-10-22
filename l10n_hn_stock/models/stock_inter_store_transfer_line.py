# -*- coding: utf-8 -*-
# Part of l10n_hn_stock. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockInterStoreTransferLine(models.Model):
    _name = "stock.inter.store.transfer.line"
    _description = "Línea de Traslado entre Tiendas"
    _order = "sequence, id"

    transfer_id = fields.Many2one(
        "stock.inter.store.transfer",
        string="Traslado",
        required=True,
        ondelete="cascade",
    )
    allowed_product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Productos permitidos en origen",
        related="transfer_id.allowed_product_ids",
        readonly=True,
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    sequence_number = fields.Integer(
        string="#",
        compute="_compute_sequence_number",
        help="Número de línea",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="transfer_id.company_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain="[('type', 'in', ('product', 'consu')), ('id', 'in', allowed_product_ids)]",
    )
    product_tracking = fields.Selection(
        related="product_id.tracking",
        string="Trazado",
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lote / Serie",
        check_company=True,
        domain="[('product_id', '=', product_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    product_uom_qty = fields.Float(
        string="Cantidad",
        required=True,
        digits="Product Unit of Measure",
    )
    product_uom = fields.Many2one(
        "uom.uom",
        string="UdM",
        related="product_id.uom_id",
        readonly=True,
    )
    qty_available = fields.Float(
        string="Disponible",
        compute="_compute_qty_available",
        digits="Product Unit of Measure",
        help="Cantidad disponible (libre) en la ubicación origen del traslado; con lote, del lote en origen.",
    )
    gn_labhospy_supplier_id = fields.Many2one(
        comodel_name="gn.labhospy.supplier",
        string="Proveedor (LabHosPy)",
        related="product_id.gn_labhospy_supplier_id",
        readonly=True,
    )
    gn_labhospy_catalog_code = fields.Char(
        string="Código de Catálogo",
        related="product_id.gn_labhospy_catalog_code",
        readonly=True,
    )
    gn_labhospy_is_controlled = fields.Boolean(
        string="Producto controlado",
        related="product_id.product_tmpl_id.gn_labhospy_is_controlled",
        readonly=True,
    )
    @api.depends("transfer_id", "transfer_id.line_ids", "transfer_id.line_ids.sequence")
    def _compute_sequence_number(self):
        """Calcula el número de línea siguiendo el patrón de order_line_sequences."""
        for transfer in self.mapped("transfer_id"):
            sequence_number = 1
            for line in transfer.line_ids.sorted(key=lambda l: (l.sequence, l.id or 0)):
                if line in self:
                    line.sequence_number = sequence_number
                sequence_number += 1

    @api.depends(
        "product_id",
        "lot_id",
        "transfer_id",
        "transfer_id.location_src_id",
        "transfer_id.state",
    )
    def _compute_qty_available(self):
        """Cantidad libre en ubicación origen (o del lote en origen); visible en todos los estados."""
        for line in self:
            if line.product_id and line.transfer_id and line.transfer_id.location_src_id:
                line.qty_available = line._get_free_qty_at_origin()
            else:
                line.qty_available = 0.0

    def _get_free_qty_at_origin(self):
        """Cantidad libre en origen: total del producto o, con lote, del lote concreto."""
        self.ensure_one()
        if (
            not self.product_id
            or not self.transfer_id
            or not self.transfer_id.location_src_id
        ):
            return 0.0
        if self.product_id.tracking in ("lot", "serial") and self.lot_id:
            return self.env["stock.quant"]._get_available_quantity(
                self.product_id,
                self.transfer_id.location_src_id,
                lot_id=self.lot_id,
                strict=True,
            )
        return self.product_id.with_context(
            location=self.transfer_id.location_src_id.id
        ).free_qty

    def _ensure_qty_not_exceed_available(self):
        """Bloquea si cantidad > disponible en origen (borrador)."""
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for line in self:
            if line.transfer_id.state != "draft":
                continue
            if not line.product_id or not line.transfer_id.location_src_id:
                continue
            free = line._get_free_qty_at_origin()
            if float_compare(line.product_uom_qty, free, precision_digits=precision) > 0:
                raise ValidationError(
                    _(
                        "La cantidad (%(qty)s) no puede ser mayor que la disponible "
                        "en origen (%(avail)s) para el producto %(product)s.",
                        qty=line.product_uom_qty,
                        avail=free,
                        product=line.product_id.display_name,
                    )
                )

    @api.constrains("product_uom_qty", "product_id", "transfer_id")
    def _check_qty_not_exceed_available(self):
        self._ensure_qty_not_exceed_available()

    @api.constrains("product_id", "lot_id", "product_uom_qty")
    def _check_lot_required_and_serial_qty(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for line in self:
            if not line.product_id:
                continue
            if line.product_id.tracking == "none" and line.lot_id:
                raise ValidationError(
                    _(
                        "No indique lote/serie en %(product)s: el producto no usa trazado por lote/serie.",
                        product=line.product_id.display_name,
                    )
                )
            if line.product_id.tracking in ("lot", "serial"):
                if not line.lot_id:
                    raise ValidationError(
                        _(
                            "Debe indicar lote/serie en la línea de %(product)s "
                            "para que el traslado conserve el coste del lote al validar el inventario.",
                            product=line.product_id.display_name,
                        )
                    )
            if line.product_id.tracking == "serial" and not float_is_zero(
                line.product_uom_qty, precision_digits=precision
            ) and float_compare(
                line.product_uom_qty, 1.0, precision_digits=precision
            ) != 0:
                raise ValidationError(
                    _(
                        "Con trazado por número de serie, la cantidad en cada línea "
                        "debe ser 1. Use varias líneas para varias unidades de %(product)s.",
                        product=line.product_id.display_name,
                    )
                )
            if line.lot_id and line.lot_id.product_id != line.product_id:
                raise ValidationError(
                    _(
                        "El lote «%(lot)s» no corresponde al producto «%(product)s».",
                        lot=line.lot_id.display_name,
                        product=line.product_id.display_name,
                    )
                )

    @api.onchange("product_uom_qty")
    def _onchange_product_uom_qty(self):
        if (
            not self.product_id
            or not self.transfer_id
            or not self.transfer_id.location_src_id
            or self.transfer_id.state != "draft"
        ):
            return
        free = self._get_free_qty_at_origin()
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        if float_compare(self.product_uom_qty, free, precision_digits=precision) > 0:
            return {
                "warning": {
                    "title": _("Cantidad mayor al disponible"),
                    "message": _(
                        "La cantidad (%(qty)s) supera lo disponible en origen (%(avail)s) "
                        "para %(product)s. Ajuste la cantidad antes de guardar.",
                        qty=self.product_uom_qty,
                        avail=free,
                        product=self.product_id.display_name,
                    ),
                }
            }

    def _find_duplicate_line_in_transfer(self, line):
        """Otra línea del mismo traslado que repite producto o el par (producto, lote)."""
        Line = self.env["stock.inter.store.transfer.line"]
        line.ensure_one()
        if not line.product_id or not line.transfer_id:
            return Line
        for other in line.transfer_id.line_ids:
            # Misma fila: usar == (no "is") para que coincida con el mismo registro
            # en onchange, donde a veces hay dos referencias a la línea virtual (NewId).
            if other == line:
                continue
            if not other.product_id or other.product_id != line.product_id:
                continue
            if line.product_id.tracking == "none":
                return other
            if not line.lot_id or not other.lot_id:
                continue
            if line.lot_id == other.lot_id:
                return other
        return Line

    def _line_is_duplicate_in_transfer(self, line):
        """Producto sin trazado: una sola línea por producto. Con lote/serie: una por (producto, lote)."""
        return bool(self._find_duplicate_line_in_transfer(line))

    @api.onchange("product_id")
    def _onchange_product_lot_and_duplicate(self):
        """Limpia lote al cambiar producto; evita duplicar producto o par (producto, lote)."""
        if not self.env.context.get("skip_lot_onchange"):
            self.lot_id = False
        if not self.product_id or not self.transfer_id:
            return {}
        other = self._find_duplicate_line_in_transfer(self)
        if other:
            product_name = self.product_id.display_name
            product_ref = self.product_id.default_code or "Sin referencia"
            doc_name = self.transfer_id.name or _("(sin referencia)")
            self.product_id = False
            return {
                "warning": {
                    "title": _("Línea duplicada"),
                    "message": _(
                        "El producto '%(product)s' (Ref: %(ref)s) ya figura con la misma trazabilidad "
                        "en la línea %(line_no)s del traslado %(doc)s.\n\n"
                        "Ajuste la cantidad o use otra fila con distinto lote/serie según corresponda.",
                        product=product_name,
                        ref=product_ref,
                        line_no=other.sequence_number,
                        doc=doc_name,
                    ),
                }
            }
        return {}

    @api.onchange("lot_id")
    def _onchange_lot_duplicate(self):
        if not self.lot_id or not self.product_id or not self.transfer_id:
            return {}
        other = self._find_duplicate_line_in_transfer(self)
        if other:
            lot_name = self.lot_id.display_name
            doc_name = self.transfer_id.name or _("(sin referencia)")
            self.lot_id = False
            return {
                "warning": {
                    "title": _("Lote / serie duplicado"),
                    "message": _(
                        "El lote o número de serie «%(lot)s» ya figura en la línea %(line_no)s "
                        "del traslado %(doc)s (mismo producto).",
                        lot=lot_name,
                        line_no=other.sequence_number,
                        doc=doc_name,
                    ),
                }
            }
        return {}

    @api.constrains("product_id", "lot_id", "transfer_id")
    def _check_duplicate_product(self):
        """Una sola línea por producto sin trazado; con trazado, una por (producto, lote)."""
        for line in self:
            if not line.product_id or not line.transfer_id:
                continue
            other = line._find_duplicate_line_in_transfer(line)
            if other:
                if line.product_id.tracking == "none":
                    raise ValidationError(
                        _(
                            "No se puede agregar el producto «%(name)s» dos veces en el traslado %(doc)s: "
                            "ya figura en la línea %(line_no)s.\n\n"
                            "Modifique la cantidad en la línea existente.",
                            name=line.product_id.display_name,
                            doc=line.transfer_id.name or _("(sin referencia)"),
                            line_no=other.sequence_number,
                        )
                    )
                raise ValidationError(
                    _(
                        "El producto «%(name)s» con el lote/serie indicado ya figura en la línea %(line_no)s "
                        "del traslado %(doc)s.",
                        name=line.product_id.display_name,
                        line_no=other.sequence_number,
                        doc=line.transfer_id.name or _("(sin referencia)"),
                    )
                )
