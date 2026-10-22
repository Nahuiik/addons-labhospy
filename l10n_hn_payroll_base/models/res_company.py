# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    header_memb = fields.Boolean(string="Papel membretado", help="Oculta logo y datos de cabecera en PDFs de constancia.")

    payslip_report_template = fields.Selection(
        [
            ("standard", "Standard"),
            ("modern", "Modern"),
            ("classic", "Classic"),
            ("fancy", "Fancy"),
        ],
        string="Payslip PDF Layout",
        default="standard",
        help="Layout used by professional payslip PDF reports.",
    )
