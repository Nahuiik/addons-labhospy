# Copyright 2021 ForgeFlow, S.L.
# Copyright 2022 Vauxoo, S.A.
# Copyright 2025 Grupo Nahuiik
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        domain="[('is_customer', '=', True)] if partner_type == 'customer' else [('is_supplier', '=', True)] if partner_type == 'supplier' else []",
    )
