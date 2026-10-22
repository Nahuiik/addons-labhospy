# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sale_receipt_default_journal_id = fields.Many2one(
        "account.journal",
        string="Diario por defecto para recibos",
        domain="[('company_id', '=', company_id), ('type', 'in', ('cash','bank'))]",
        config_parameter="sale_receipt.default_journal_id",
    )
    sale_receipt_default_payment_journal_id = fields.Many2one(
        "account.journal",
        string="Método de pago por defecto",
        domain="[('company_id', '=', company_id), ('type', 'in', ('cash','bank'))]",
        config_parameter="sale_receipt.default_payment_method_journal_id",
    )
    sale_receipt_auto_description = fields.Boolean(
        string="Autocompletar descripción con factura",
        config_parameter="sale_receipt.auto_description",
        default=True,
    )
