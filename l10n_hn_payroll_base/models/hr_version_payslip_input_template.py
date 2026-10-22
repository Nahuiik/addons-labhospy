# -*- coding: utf-8 -*-
"""Default payslip inputs per contract version (template-friendly, CE)."""

from odoo import fields, models


class HrVersionPayslipInputTemplate(models.Model):
    _name = "hr.version.payslip.input.template"
    _description = "Contract default payslip input"
    _order = "version_id, sequence, id"

    version_id = fields.Many2one(
        "hr.version",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    input_type_id = fields.Many2one(
        "hr.payslip.input.type",
        string="Input type",
        required=True,
        ondelete="restrict",
    )
    default_amount = fields.Float(
        string="Default amount",
        digits=(16, 4),
        default=0.0,
        help="Prefilled amount (or quantity when the type is “quantity”) on draft payslip input lines.",
    )

    _sql_constraints = [
        (
            "unique_version_input_type",
            "unique(version_id, input_type_id)",
            "Each input type can only appear once per contract version.",
        ),
    ]
