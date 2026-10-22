from odoo import _, models
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _get_available_quantity(
        self,
        product_id,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=False,
        allow_negative=False,
    ):
        if (
            location_id
            and not location_id.allow_negative_stock
            and not location_id.check_serial_no
            and product_id.tracking == "serial"
        ):
            lot_id = None

        res = super()._get_available_quantity(
            product_id=product_id,
            location_id=location_id,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
            allow_negative=allow_negative,
        )

        company = self.mapped("company_id") or self.env.company
        if len(company) > 1:
            raise UserError(_("You cannot search for available quantity across several companies."))

        if not company.no_negative_stock:
            return res

        if self.env.context.get("restricted_picking_type_code") == "incoming":
            return res

        if (
            location_id
            and not location_id.allow_negative_stock
            and res < 0.0
            and location_id.usage == "internal"
        ):
            err = _(
                "Has configurado evitar inventario negativo. Quedan %(qty)s unidades de %(product)s "
                "en la ubicación %(location)s. Ajusta tus cantidades o corrige el inventario con un ajuste."
            ) % {
                "qty": res,
                "product": product_id.display_name,
                "location": location_id.display_name,
            }
            raise UserError(err)

        return res


