# -*- coding: utf-8 -*-
# Part of l10n_hn_stock. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.tools.float_utils import float_compare


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Visibles en chatter: prioridad numérica más alta = más relevante en el resumen
    name = fields.Char(tracking=100)
    active = fields.Boolean(tracking=20)
    type = fields.Selection(tracking=100)
    sale_ok = fields.Boolean(tracking=20)
    purchase_ok = fields.Boolean(tracking=20)
    default_code = fields.Char(tracking=20)
    barcode = fields.Char(tracking=20)
    description_sale = fields.Text(tracking=20)

    categ_id = fields.Many2one(tracking=100)
    list_price = fields.Float(tracking=100)
    # Costo: sin tracking ORM; suele cambiar por valoración en sudo() y no dejaba rastro.
    standard_price = fields.Float(tracking=False)

    landed_cost_ok = fields.Boolean(tracking=40)
    split_method_landed_cost = fields.Selection(tracking=40)

    def _track_get_default_log_message(self, changes):
        res = (super()._track_get_default_log_message(changes) or "").strip()
        if not changes:
            return res
        self.ensure_one()
        parts = []
        if "landed_cost_ok" in changes or "split_method_landed_cost" in changes:
            parts.append(
                _(
                    "Se actualizó la configuración de coste en destino (landed cost)."
                )
            )
        if not parts:
            return res
        lead = " ".join(parts)
        if res:
            return f"{lead}\n\n{res}"
        return lead

    def write(self, vals):
        if (
            "standard_price" not in vals
            or self.env.context.get("l10n_hn_skip_standard_price_chatter")
        ):
            return super().write(vals)
        before = {t.id: t.standard_price for t in self}
        res = super().write(vals)
        self._l10n_hn_chatter_standard_price_template(before)
        return res

    def _l10n_hn_chatter_standard_price_template(self, before_by_id):
        prec = self.env["decimal.precision"].precision_get("Product Price")
        hint = self.env.context.get("l10n_hn_standard_price_chatter_hint")
        for tmpl in self:
            old = before_by_id.get(tmpl.id)
            if old is None:
                continue
            new = tmpl.standard_price
            if float_compare(old, new, precision_digits=prec) == 0:
                continue
            sym = tmpl.cost_currency_id.symbol or ""
            body = _(
                "Cambio de precio de costo: %(old)s → %(new)s %(sym)s",
                old=old,
                new=new,
                sym=sym,
            )
            if hint:
                body = f"{body}\n<em>{hint}</em>"
            tmpl.message_post(body=body, subtype_xmlid="mail.mt_note")


class ProductProduct(models.Model):
    _inherit = "product.product"

    default_code = fields.Char(tracking=20)
    barcode = fields.Char(tracking=20)
    active = fields.Boolean(tracking=20)

    standard_price = fields.Float(tracking=False)

    def write(self, vals):
        if "standard_price" not in vals or self.env.context.get(
            "l10n_hn_skip_standard_price_chatter"
        ):
            return super().write(vals)
        before = {p.id: p.standard_price for p in self}
        res = super().write(vals)
        self._l10n_hn_chatter_standard_price_variant(before)
        return res

    def _l10n_hn_chatter_standard_price_variant(self, before_by_id):
        prec = self.env["decimal.precision"].precision_get("Product Price")
        hint = self.env.context.get("l10n_hn_standard_price_chatter_hint")
        for product in self:
            old = before_by_id.get(product.id)
            if old is None:
                continue
            new = product.standard_price
            if float_compare(old, new, precision_digits=prec) == 0:
                continue
            sym = product.cost_currency_id.symbol or ""
            body = _(
                "Cambio de precio de costo: %(old)s → %(new)s %(sym)s",
                old=old,
                new=new,
                sym=sym,
            )
            if hint:
                body = f"{body}\n<em>{hint}</em>"
            product.message_post(body=body, subtype_xmlid="mail.mt_note")
