# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    gn_bank_account_type = fields.Selection(
        selection=[
            ("savings", "Ahorro"),
            ("current", "Corriente"),
            ("checks", "Cheques"),
        ],
        string="Tipo de cuenta",
    )

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if "bank_id" not in fields_list or defaults.get("bank_id"):
            return defaults
        country = self._gn_get_default_bank_country(defaults)
        if not country:
            return defaults
        company = self._gn_get_default_bank_company(defaults)
        default_bank = self._gn_search_default_bank(country, company)
        if default_bank:
            defaults["bank_id"] = default_bank.id
        return defaults

    @api.model
    def _gn_search_default_bank(self, country, company=None):
        domain = [
            ("country", "=", country.id),
            ("gn_is_default_bank", "=", True),
        ]
        if company and "company_id" in self.env["res.bank"]._fields:
            domain.append(("company_id", "=", company.id))
        return self.env["res.bank"].search(domain, limit=1)

    @api.model
    def _gn_get_default_bank_company(self, defaults):
        partner_id = defaults.get("partner_id") or self.env.context.get("default_partner_id")
        if partner_id:
            partner = self.env["res.partner"].browse(partner_id)
            if partner.company_id:
                return partner.company_id
        company_id = (
            defaults.get("company_id")
            or self.env.context.get("default_company_id")
            or self.env.company.id
        )
        return self.env["res.company"].browse(company_id) if company_id else self.env.company

    @api.model
    def _gn_get_default_bank_country(self, defaults):
        partner_id = defaults.get("partner_id") or self.env.context.get("default_partner_id")
        if partner_id:
            partner = self.env["res.partner"].browse(partner_id)
            if partner.country_id:
                return partner.country_id
        company_id = (
            defaults.get("company_id")
            or self.env.context.get("default_company_id")
            or self.env.company.id
        )
        if company_id:
            company = self.env["res.company"].browse(company_id)
            if company.country_id:
                return company.country_id
        return self.env.company.country_id
