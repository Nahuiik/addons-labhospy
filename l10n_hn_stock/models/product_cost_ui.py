# -*- coding: utf-8 -*-
"""Visibilidad y edición de costo (standard_price) según grupos de l10n_hn_stock."""

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_hn_standard_price_readonly = fields.Boolean(
        compute="_compute_l10n_hn_standard_price_readonly",
        compute_sudo=False,
        help="Técnico: la interfaz deja el costo en solo lectura si el usuario no puede "
        "editarlo (grupo Editar costo de producto).",
    )

    @api.depends_context("uid")
    def _compute_l10n_hn_standard_price_readonly(self):
        can_edit = self.env.user.has_group("l10n_hn_stock.group_edit_product_cost")
        ro = not can_edit
        for tmpl in self:
            tmpl.l10n_hn_standard_price_readonly = ro


class ProductProduct(models.Model):
    _inherit = "product.product"

    l10n_hn_standard_price_readonly = fields.Boolean(
        compute="_compute_l10n_hn_standard_price_readonly",
        compute_sudo=False,
    )

    @api.depends_context("uid")
    def _compute_l10n_hn_standard_price_readonly(self):
        can_edit = self.env.user.has_group("l10n_hn_stock.group_edit_product_cost")
        ro = not can_edit
        for product in self:
            product.l10n_hn_standard_price_readonly = ro
