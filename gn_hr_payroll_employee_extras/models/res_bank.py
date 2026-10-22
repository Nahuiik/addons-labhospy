# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResBank(models.Model):
    _inherit = "res.bank"

    gn_is_default_bank = fields.Boolean(
        string="Banco por default",
        default=False,
        copy=False,
    )

    @api.constrains("gn_is_default_bank", "country")
    def _check_gn_single_default_bank_per_country(self):
        for bank in self.filtered("gn_is_default_bank"):
            if not bank.country:
                raise ValidationError(
                    _("Debe indicar el país antes de marcar el banco como predeterminado.")
                )
            if self.search_count(
                [
                    ("country", "=", bank.country.id),
                    ("gn_is_default_bank", "=", True),
                    ("id", "!=", bank.id),
                ]
            ):
                raise ValidationError(_("Solo puede haber un banco por default por país."))

    @api.model_create_multi
    def create(self, vals_list):
        banks = super().create(vals_list)
        banks.filtered("gn_is_default_bank")._gn_clear_other_default_banks()
        return banks

    def write(self, vals):
        res = super().write(vals)
        if "gn_is_default_bank" in vals or "country" in vals:
            self.filtered("gn_is_default_bank")._gn_clear_other_default_banks()
        return res

    def _gn_clear_other_default_banks(self):
        for bank in self.filtered(lambda b: b.gn_is_default_bank and b.country):
            others = self.search(
                [
                    ("country", "=", bank.country.id),
                    ("gn_is_default_bank", "=", True),
                    ("id", "!=", bank.id),
                ]
            )
            if others:
                others.write({"gn_is_default_bank": False})
