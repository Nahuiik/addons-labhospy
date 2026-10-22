# -*- coding: utf-8 -*-
"""
Odoo Proprietary License v1.0.

see License:
https://www.odoo.com/documentation/user/15.0/legal/licenses/licenses.html#odoo-apps
# Copyright ©2022 Bernard K. Too<bernard.too@optima.co.ke>
"""
from odoo import fields, models


class AccountJournalFooter(models.Model):
    _inherit = "account.journal"

    display_on_footer = fields.Boolean(
        "Show in Invoices Footer",
        help="Display this bank account on the footer of printed documents like invoices and sales orders.",
    )
