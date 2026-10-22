# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    land_cost_cancel_modes = fields.Selection(
        [
            ("cancel", "Cancel only"),
            ("cancel_draft", "Cancel and reset to draft"),
            ("cancel_delete", "Cancel and delete"),
        ],
        string="Landed cost cancellation mode",
        default="cancel",
        help=(
            "Choose what happens when you cancel a validated landed cost from the form or the list."
        ),
        config_parameter="cancel_landed_cost_odoo.land_cost_cancel_modes",
    )
