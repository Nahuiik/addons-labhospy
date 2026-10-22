# -*- coding: utf-8 -*-
"""Payroll app menus: align visibility with Enterprise-like folder trees on Odoo 19."""

from odoo import api, models, tools


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    @tools.ormcache("frozenset(self.env.user._get_group_ids())", "debug")
    def _visible_menu_ids(self, debug=False):
        visible_ids = set(super()._visible_menu_ids(debug=debug))
        root = self.env.ref("l10n_hn_payroll_base.menu_hn_payroll_root", raise_if_not_found=False)
        if not root:
            return frozenset(visible_ids)

        user_gids = frozenset(self.env.user._get_group_ids())
        Menu = self.sudo()
        root_id = root.id

        # Odoo stops walking up to parent folders when the parent is not in the initial
        # `menu_ids` set (stricter or different group_ids than a visible child). Then
        # section roots like «Nómina HN» never become visible. See base `ir.ui.menu`.
        folders = Menu.search(
            [
                ("id", "child_of", root_id),
                ("id", "!=", root_id),
                ("action", "=", False),
            ]
        )
        for folder in folders:
            if folder.group_ids:
                if not (set(folder.group_ids._ids) & user_gids):
                    continue
            subtree_ids = set(Menu.search([("id", "child_of", folder.id)]).ids)
            if subtree_ids & visible_ids:
                visible_ids.add(folder.id)

        return frozenset(visible_ids)
