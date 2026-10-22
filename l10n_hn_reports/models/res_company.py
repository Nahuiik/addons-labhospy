# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _hn_fiscal_reports_company_ids(self):
        """Compañía + filiales + matrices (asientos en empresa padre)."""
        self.ensure_one()
        Company = self.env['res.company'].sudo()
        companies = Company.browse(self.id)
        companies |= Company.search([('id', 'child_of', self.id)])
        parent = self.parent_id
        while parent:
            companies |= parent
            parent = parent.parent_id
        return companies.ids

    hn_isr_report_account_ids = fields.Many2many(
        'account.account',
        'res_company_hn_isr_report_account_rel',
        'company_id',
        'account_id',
        string='Cuentas para reporte ISR',
        domain="[('company_ids', 'parent_of', id)]",
        help='Cuentas sugeridas para el resumen mensual de control del Impuesto sobre la renta '
             '(deducciones, pagos provisionales, impuesto por pagar, etc.).',
    )

    hn_isv_closing_journal_id = fields.Many2one(
        'account.journal',
        string='Diario cierre ISV (Honduras)',
        check_company=True,
        domain="[('company_id', '=', id)]",
    )
    hn_isv_closing_debit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta débito cierre ISV',
        check_company=True,
        domain="[('company_ids', 'parent_of', id)]",
    )
    hn_isv_closing_credit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta crédito cierre ISV',
        check_company=True,
        domain="[('company_ids', 'parent_of', id)]",
    )
