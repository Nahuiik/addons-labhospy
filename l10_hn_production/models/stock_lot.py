from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockLot(models.Model):
    _inherit = "stock.lot"

    hn_content_capacity = fields.Float(
        string="Contenido inicial",
        digits="Product Unit of Measure",
        copy=False,
        help="Contenido total del envase cuando está sellado.",
    )
    hn_content_remaining = fields.Float(
        string="Contenido restante",
        digits="Product Unit of Measure",
        copy=False,
        help="Contenido aún disponible dentro del envase.",
    )
    hn_container_open = fields.Boolean(
        string="Envase abierto",
        copy=False,
        help="Indica si el envase ya fue abierto y tiene consumo parcial.",
    )
    hn_container_content_uom_id = fields.Many2one(
        related="product_id.hn_container_content_uom_id",
        readonly=True,
    )
    hn_container_tracking = fields.Boolean(
        related="product_id.hn_container_tracking",
        readonly=True,
    )

    @api.model
    def _hn_next_lot_name(self, product, company=None, lot_date=None):
        """Genera el siguiente lote con formato AAAA-MM-DD-00001."""
        company = company or self.env.company
        lot_date = lot_date or fields.Date.context_today(self)
        prefix = lot_date.strftime("%Y-%m-%d-")
        lots = self.search(
            [
                ("product_id", "=", product.id),
                ("name", "=like", prefix + "%"),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ]
        )
        max_num = 0
        for lot in lots:
            suffix = lot.name[len(prefix) :]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
        return "%s%05d" % (prefix, max_num + 1)

    def _hn_init_container_content(self):
        for lot in self.filtered(lambda l: l.product_id._hn_is_container()):
            capacity = lot.product_id.hn_container_content_qty
            vals = {}
            if float_is_zero(lot.hn_content_capacity, precision_rounding=0.0001):
                vals["hn_content_capacity"] = capacity
            if float_is_zero(
                lot.hn_content_remaining,
                precision_rounding=0.0001,
            ) and not lot.hn_container_open:
                vals["hn_content_remaining"] = capacity
            if vals:
                lot.write(vals)

    def _hn_content_rounding(self):
        self.ensure_one()
        uom = self.product_id.hn_container_content_uom_id
        return uom.rounding if uom else 0.0001

    def _hn_consume_content(self, qty):
        self.ensure_one()
        self._hn_init_container_content()
        rounding = self._hn_content_rounding()
        if float_compare(qty, 0.0, precision_rounding=rounding) <= 0:
            return
        if float_compare(
            qty,
            self.hn_content_remaining,
            precision_rounding=rounding,
        ) > 0:
            raise UserError(
                _(
                    "El lote «%(lot)s» solo tiene %(remain)s %(uom)s disponibles; "
                    "se solicitaron %(need)s.",
                    lot=self.display_name,
                    remain=self.hn_content_remaining,
                    need=qty,
                    uom=self.product_id.hn_container_content_uom_id.display_name,
                )
            )
        remaining = self.hn_content_remaining - qty
        vals = {
            "hn_content_remaining": remaining,
            "hn_container_open": True,
        }
        if float_is_zero(remaining, precision_rounding=rounding):
            vals["hn_content_remaining"] = 0.0
        self.write(vals)
