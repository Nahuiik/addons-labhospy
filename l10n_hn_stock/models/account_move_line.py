from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    hn_readonly_price = fields.Boolean(
        string="Locked Price",
        compute="_compute_hn_readonly_price",
    )

    @api.model
    def _is_invoice_price_locked_for_user(self):
        user = self.env.user
        if user.has_group("l10n_hn_stock.group_allow_sell_below_cost"):
            return False
        has_user_group = user.has_group(
            "l10n_hn_stock.group_allow_edit_sale_price_invoice_user"
        )
        has_manager_group = user.has_group(
            "l10n_hn_stock.group_allow_edit_sale_price_invoice"
        )
        return has_user_group and not has_manager_group

    @api.depends_context("uid")
    def _compute_hn_readonly_price(self):
        lock_price = self._is_invoice_price_locked_for_user()
        for line in self:
            move = line.move_id
            line.hn_readonly_price = bool(
                lock_price
                and move
                and move.move_type in ("out_invoice", "out_refund")
            )

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
        if self.env.su or "price_unit" not in vals:
            return

        if not self._is_invoice_price_locked_for_user():
            return

        allowed_move_types = ("out_invoice", "out_refund")

        if creating:
            move_type = vals.get("move_type") or self.env.context.get(
                "default_move_type"
            )
            if not move_type and vals.get("move_id"):
                move = self.env["account.move"].browse(vals["move_id"])
                move_type = move.move_type

            if move_type not in allowed_move_types:
                return

            raise UserError(
                _(
                    "El permiso de restricción de precio de venta está activo, no puedes modificar el precio en las facturas de cliente."
                )
            )

        relevant_lines = self.filtered(
            lambda line: line.move_id.move_type in allowed_move_types
        )
        if not relevant_lines:
            return

        if any(line.price_unit != vals.get("price_unit") for line in relevant_lines):
            raise UserError(
                _(
                    "El permiso de restricción de precio de venta está activo, no puedes modificar el precio en las facturas de cliente."
                )
            )

    def _check_price_vs_cost_onchange(self):
        if (
            self.env.su
            or self.env.user.has_group("l10n_hn_stock.group_allow_sell_below_cost")
        ):
            return

        allowed_move_types = ("out_invoice", "out_refund")
        warning = None

        for line in self:
            move = line.move_id
            if not move or move.move_type not in allowed_move_types:
                continue
            if line.display_type:
                continue
            product = line.product_id
            product_uom = line.product_uom_id or getattr(line, "product_uom", False)
            if not product or not product_uom:
                continue
            cost_price = self._get_cost_price(move, product, product_uom)
            currency = (
                move.currency_id
                or move.company_currency_id
                or self.env.company.currency_id
            )
            if (
                currency
                and float_compare(
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
        allowed_move_types = ("out_invoice", "out_refund")

        if creating:
            move = self._get_move_from_vals(vals)
            product = self._get_product_from_vals(vals)
            product_uom = self._get_uom_from_vals(vals, product)
            if (
                not move
                or move.move_type not in allowed_move_types
                or not product
                or not product_uom
            ):
                return
            self._raise_if_price_below_cost(move, product, product_uom, price_unit)
            return

        relevant_lines = self.filtered(lambda line: line.move_id.move_type in allowed_move_types)
        for line in relevant_lines:
            move = line.move_id
            product = (
                self.env["product.product"].browse(vals["product_id"])
                if vals.get("product_id")
                else line.product_id
            )
            if not product:
                continue
            if vals.get("product_uom_id") or vals.get("product_uom"):
                uom_val = vals.get("product_uom_id") or vals.get("product_uom")
                product_uom = self.env["uom.uom"].browse(uom_val)
            else:
                product_uom = line.product_uom_id
            if not product_uom:
                continue
            self._raise_if_price_below_cost(move, product, product_uom, price_unit)

    def _get_move_from_vals(self, vals):
        move_id = vals.get("move_id")
        if move_id:
            return self.env["account.move"].browse(move_id)
        move_type = vals.get("move_type") or self.env.context.get("default_move_type")
        if not move_type:
            return self.env["account.move"]
        # Create a pseudo move with minimal data for currency evaluation
        company = self.env.company
        currency = self.env["res.currency"].browse(vals.get("currency_id")) or company.currency_id
        return self.env["account.move"].new(
            {
                "company_id": company.id,
                "currency_id": currency.id,
                "move_type": move_type,
            }
        )

    def _get_product_from_vals(self, vals):
        product_id = vals.get("product_id") or self.env.context.get("default_product_id")
        if not product_id:
            return self.env["product.product"]
        return self.env["product.product"].browse(product_id)

    def _get_uom_from_vals(self, vals, product):
        uom_id = vals.get("product_uom_id") or vals.get("product_uom") or self.env.context.get(
            "default_product_uom"
        )
        if uom_id:
            return self.env["uom.uom"].browse(uom_id)
        if product:
            return product.uom_id
        return self.env["uom.uom"]

    def _raise_if_price_below_cost(self, move, product, product_uom, price_unit):
        cost_price = self._get_cost_price(move, product, product_uom)
        currency = move.currency_id or move.company_currency_id or self.env.company.currency_id
        if currency and float_compare(
            price_unit, cost_price, precision_rounding=currency.rounding
        ) < 0:
            raise UserError(_("No puedes vender por debajo del costo."))

    def _get_cost_price(self, move, product, product_uom):
        if not product:
            return 0.0
        company = move.company_id or self.env.company
        product_company = product.with_company(company)
        cost_price = product_company.standard_price
        product_uom_origin = product_company.uom_id
        if product_uom and product_uom != product_uom_origin:
            cost_price = product_uom_origin._compute_price(cost_price, product_uom)
        company_currency = company.currency_id
        move_currency = move.currency_id or company_currency
        if company_currency and move_currency and company_currency != move_currency:
            date = move.invoice_date or fields.Date.context_today(move)
            cost_price = company_currency._convert(
                cost_price, move_currency, company, date
            )
        return cost_price
