# -*- coding: utf-8 -*-
"""Asigna etiquetas SAR 904 (casilla_904) a líneas de reparto de impuestos del plan HN."""

from odoo import models, _
from odoo.exceptions import UserError


class L10nHnReports904TaxSync(models.AbstractModel):
    _name = 'l10n_hn_reports.904_tax_sync'
    _description = 'Sincronizar reparto de impuestos HN con etiquetas 904'

    def _ref_tag(self, xmlid_suffix):
        return self.env.ref(
            'l10n_hn_reports.%s' % xmlid_suffix,
            raise_if_not_found=False,
        )

    def _specs(self):
        """Lista de reglas para etiquetar repartos de impuesto (type_tax_use, amount, name_kind, xmlids de tags)."""
        return [
            {
                'type_tax_use': 'sale',
                'amount': 15.0,
                'price_include': False,
                'name_kind': 'isv',
                'base_xmlids': ['sar_tag_904_1'],
                'tax_xmlids': ['sar_tag_904_21'],
            },
            {
                'type_tax_use': 'sale',
                'amount': 15.0,
                'price_include': True,
                'name_kind': 'isv',
                'base_xmlids': ['sar_tag_904_1'],
                'tax_xmlids': ['sar_tag_904_21'],
            },
            {
                'type_tax_use': 'sale',
                'amount': 0.0,
                'price_include': False,
                'name_kind': 'exento',
                'base_xmlids': ['sar_tag_904_2'],
                'tax_xmlids': [],
            },
            {
                'type_tax_use': 'sale',
                'amount': 0.0,
                'price_include': False,
                'name_kind': 'exonerado',
                'base_xmlids': ['sar_tag_904_3'],
                'tax_xmlids': [],
            },
            {
                'type_tax_use': 'purchase',
                'amount': 15.0,
                'price_include': False,
                'name_kind': 'isv',
                'base_xmlids': ['sar_tag_904_11'],
                'tax_xmlids': ['sar_tag_904_31'],
            },
            {
                'type_tax_use': 'purchase',
                'amount': 15.0,
                'price_include': True,
                'name_kind': 'isv',
                'base_xmlids': ['sar_tag_904_11'],
                'tax_xmlids': ['sar_tag_904_31'],
            },
            {
                'type_tax_use': 'purchase',
                'amount': 0.0,
                'price_include': False,
                'name_kind': 'exento',
                'base_xmlids': ['sar_tag_904_13'],
                'tax_xmlids': [],
            },
        ]

    def _name_matches_kind(self, tax, kind):
        n = (tax.name or '').lower()
        if kind == 'isv' or kind == 'isv_incl':
            if '15' in n or 'isv' in n:
                return True
            # 15 % porcentual típico ISV HN aunque el nombre sea abreviado (p. ej. «G»).
            return (
                tax.amount_type == 'percent'
                and float(tax.amount or 0.0) == 15.0
            )
        if kind == 'exento':
            return 'exento' in n and 'exonerado' not in n
        if kind == 'exonerado':
            return 'exonerado' in n
        return False

    def _tags_from_xmlids(self, suffixes):
        tags = self.env['account.account.tag']
        for s in suffixes:
            t = self._ref_tag(s)
            if t:
                tags |= t
        return tags

    def sync_company_taxes(self, company):
        """Aplica etiquetas 904 a impuestos de la compañía (país fiscal HN)."""
        if company.account_fiscal_country_id.code != 'HN':
            return 0
        Tax = self.env['account.tax'].with_company(company)
        updated = 0
        for spec in self._specs():
            base_tags = self._tags_from_xmlids(spec['base_xmlids'])
            tax_tags = self._tags_from_xmlids(spec['tax_xmlids'])
            if not base_tags and spec['base_xmlids']:
                raise UserError(
                    _('Faltan etiquetas 904 en la base de datos. Instale o actualice l10n_hn_reports.')
                )
            domain = [
                ('company_id', '=', company.id),
                ('country_id', '=', company.account_fiscal_country_id.id),
                ('type_tax_use', '=', spec['type_tax_use']),
                ('amount_type', '=', 'percent'),
                ('amount', '=', spec['amount']),
                ('price_include', '=', spec['price_include']),
            ]
            for tax in Tax.search(domain):
                if not self._name_matches_kind(tax, spec['name_kind']):
                    continue
                for rep in tax.repartition_line_ids:
                    if rep.repartition_type == 'base':
                        rep.tag_ids = base_tags
                    elif rep.repartition_type == 'tax' and tax_tags:
                        if rep.factor_percent:
                            rep.tag_ids = tax_tags
                updated += 1
        return updated

    def sync_all_companies(self):
        total = 0
        for company in self.env['res.company'].search([]):
            total += self.sync_company_taxes(company)
        return total
