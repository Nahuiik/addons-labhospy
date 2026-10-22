# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    asset_depreciation_ids = fields.One2many('account.asset.depreciation.line', 'move_id', string='Assets Depreciation Lines', ondelete="restrict")

    def _valid_field_parameter(self, field, name):
        return name == 'ondelete' or super()._valid_field_parameter(field, name)

    def button_cancel(self):
        for move in self:
            for line in move.asset_depreciation_ids:
                line.move_posted_check = False
        return super(AccountMove, self).button_cancel()

    def _create_assets_from_invoice_lines(self):
        """Create fixed assets / deferred revenue entries from invoice lines."""
        asset_lines = self.line_ids.filtered(
            lambda line: line.asset_category_id
            and line.display_type not in ('line_section', 'line_note')
            and line.move_id.move_type in ('in_invoice', 'in_receipt', 'out_invoice')
        )
        for line in asset_lines:
            line.asset_create()

    def action_post(self):
        for move in self:
            for depreciation_line in move.asset_depreciation_ids:
                depreciation_line.post_lines_and_close_asset()
        res = super().action_post()
        self.filtered(
            lambda move: move.move_type in ('in_invoice', 'in_receipt', 'out_invoice')
        )._create_assets_from_invoice_lines()
        return res
