# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import api, models


class IrRule(models.Model):
    _inherit = "ir.rule"

    @api.model
    def _eval_context(self):
        """Añade company_country_ids para reglas multi-compañía (p. ej. hr.license.type)."""
        res = super()._eval_context()
        company_ids = res.get("company_ids") or []
        # Entorno su: leer compañía/partner al evaluar reglas dispara ir.rule (p. ej. res.partner)
        # y reentra en _eval_context → recursión infinita.
        su_env = self.env(su=True)
        companies = su_env["res.company"].browse(company_ids)
        cids = set()
        for c in companies:
            country = c.country_id
            if not country and c.partner_id:
                country = c.partner_id.country_id
            if (
                not country
                and "account_fiscal_country_id" in c._fields
                and c.account_fiscal_country_id
            ):
                country = c.account_fiscal_country_id
            if country:
                cids.add(country.id)
        cids = list(cids)
        if not cids and res.get("company_id"):
            cc = su_env["res.company"].browse(res["company_id"])
            country = cc.country_id or (cc.partner_id.country_id if cc.partner_id else False)
            if country:
                cids = [country.id]
        res["company_country_ids"] = tuple(cids)
        return res
