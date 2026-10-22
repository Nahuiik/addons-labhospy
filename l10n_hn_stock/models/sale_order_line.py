from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    hn_readonly_price = fields.Boolean(
        string="Locked Price",
        compute="_compute_hn_readonly_price",
    )
    purchase_price = fields.Float(
        string="Cost",
        compute="_compute_purchase_price",
        digits="Product Price",
        store=True,
        readonly=True,
        copy=False,
        precompute=True,
        groups=None,
    )
    margin = fields.Float(
        string="Margin",
        compute="_compute_margin",
        digits="Product Price",
        store=True,
        precompute=True,
        groups=None,
    )
    margin_percent = fields.Float(
        string="Margin (%)",
        compute="_compute_margin",
        store=True,
        precompute=True,
        groups=None,
    )

    @api.model
    def _is_sale_price_locked_for_user(self):
        user = self.env.user
        if user.has_group("l10n_hn_stock.group_allow_sell_below_cost"):
            return False
        has_user_group = user.has_group(
            "l10n_hn_stock.group_allow_edit_sale_price_quotation_user"
        )
        has_manager_group = user.has_group(
            "l10n_hn_stock.group_allow_edit_sale_price_quotation"
        )
        return has_user_group and not has_manager_group

    @api.depends_context("uid")
    def _compute_hn_readonly_price(self):
        lock_price = self._is_sale_price_locked_for_user()
        for line in self:
            line.hn_readonly_price = lock_price

    @api.model
    def create(self, vals):
        self._check_price_unit_permission(vals, creating=True)
        self._check_price_vs_cost(vals, creating=True)
        return super().create(vals)

    def write(self, vals):
        self._check_price_unit_permission(vals, creating=False)
        self._check_price_vs_cost(vals, creating=False)
        return super().write(vals)

    @api.onchange("price_unit")
    def _onchange_price_unit_cost_check(self):
        warning = self._check_price_vs_cost_onchange()
        if warning:
            return warning

    def _check_price_unit_permission(self, vals, creating):
        if (
            not self.env.su
            and "price_unit" in vals
            and self._is_sale_price_locked_for_user()
        ):
            if creating or any(
                line.price_unit != vals.get("price_unit") for line in self
            ):
                raise UserError(
                    _(
                        "El permiso de restricción de precio de venta está activo, no puedes modificar el precio en las cotizaciones."
                    )
                )

    def _check_price_vs_cost_onchange(self):
        if (
            self.env.su
            or self.env.user.has_group("l10n_hn_stock.group_allow_sell_below_cost")
        ):
            return

        warning = None
        for line in self:
            if line.display_type:
                continue
            order = line.order_id
            product = line.product_id
            product_uom = self._get_line_uom(line)
            if not order or not product or not product_uom:
                continue
            cost_price = self._get_cost_price(order, product, product_uom)
            currency = (
                order.currency_id
                or order.company_id.currency_id
                or self.env.company.currency_id
            )
            if not currency:
                continue
            if (
                float_compare(
                    line.price_unit, cost_price, precision_rounding=currency.rounding
                )
                < 0
            ):
                line.price_unit = cost_price
                warning = {
                    "title": _("Precio menor al costo"),
                    "message": _("No puedes vender por debajo del costo."),
                }
        if warning:
            return {"warning": warning}

    def _check_price_vs_cost(self, vals, creating):
        if (
            self.env.su
            or "price_unit" not in vals
            or self.env.user.has_group("l10n_hn_stock.group_allow_sell_below_cost")
        ):
            return

        price_unit = vals["price_unit"]
        if creating:
            order = self._get_order_from_vals(vals)
            product = self._get_product_from_vals(vals)
            product_uom = self._get_uom_from_vals(vals, product)
            if not order or not product or not product_uom:
                return
            self._raise_if_price_below_cost(order, product, product_uom, price_unit)
            return

        for line in self:
            order = line.order_id
            if not order:
                continue
            product = (
                self.env["product.product"].browse(vals["product_id"])
                if vals.get("product_id")
                else line.product_id
            )
            if not product:
                continue
            product_uom = self._get_line_uom(line, vals)
            if not product_uom:
                continue
            self._raise_if_price_below_cost(order, product, product_uom, price_unit)

    def _get_order_from_vals(self, vals):
        order_id = vals.get("order_id") or self.env.context.get("default_order_id")
        if not order_id:
            return self.env["sale.order"]
        return self.env["sale.order"].browse(order_id)

    def _get_product_from_vals(self, vals):
        product_id = vals.get("product_id") or self.env.context.get("default_product_id")
        if not product_id:
            return self.env["product.product"]
        return self.env["product.product"].browse(product_id)

    def _get_uom_from_vals(self, vals, product):
        uom_id = (
            vals.get("product_uom")
            or vals.get("product_uom_id")
            or self.env.context.get("default_product_uom")
        )
        if uom_id:
            return self.env["uom.uom"].browse(uom_id)
        if product:
            return product.uom_id
        return self.env["uom.uom"]

    def _get_line_uom(self, line, vals=None):
        vals = vals or {}
        uom_val = vals.get("product_uom") or vals.get("product_uom_id")
        if uom_val:
            return self.env["uom.uom"].browse(uom_val)
        if hasattr(line, "product_uom") and line._fields.get("product_uom"):
            return line.product_uom
        return getattr(line, "product_uom_id", self.env["uom.uom"])

    def _raise_if_price_below_cost(self, order, product, product_uom, price_unit):
        cost_price = self._get_cost_price(order, product, product_uom)
        currency = order.currency_id or order.company_id.currency_id
        if not currency:
            currency = self.env.company.currency_id
        if float_compare(
            price_unit, cost_price, precision_rounding=currency.rounding
        ) < 0:
            raise UserError(_("No puedes vender por debajo del costo."))

    def _get_cost_price(self, order, product, product_uom):
        if not product:
            return 0.0
        company = order.company_id or self.env.company
        product_company = product.with_company(company)
        cost_price = product_company.standard_price
        product_uom_origin = product_company.uom_id
        if product_uom and product_uom != product_uom_origin:
            cost_price = product_uom_origin._compute_price(cost_price, product_uom)
        company_currency = company.currency_id
        order_currency = order.currency_id
        if company_currency and order_currency and company_currency != order_currency:
            date = order.date_order or fields.Date.context_today(order)
            cost_price = company_currency._convert(
                cost_price, order_currency, company, date
            )
        return cost_price



