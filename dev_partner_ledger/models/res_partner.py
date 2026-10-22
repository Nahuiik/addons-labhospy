# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Límite de líneas en la pestaña embebida (vista rápida).
    _PARTNER_LEDGER_TAB_AML_LIMIT = 200

    # Compatibilidad con vistas antiguas / etiquetas.
    enterprise_partner_ledger_available = fields.Boolean(
        string='Enterprise Partner Ledger available',
        compute='_compute_enterprise_partner_ledger_available',
    )

    @api.depends_context('uid')
    def _compute_enterprise_partner_ledger_available(self):
        available = bool(self.env['ir.module.module'].sudo().search(
            [('name', '=', 'account_reports'), ('state', '=', 'installed')], limit=1
        ))
        for partner in self:
            partner.enterprise_partner_ledger_available = available

    def _account_reports_installed(self):
        return bool(self.env['ir.module.module'].sudo().search(
            [('name', '=', 'account_reports'), ('state', '=', 'installed')], limit=1
        ))

    def _partner_ledger_receivable_payable_domain(self, partner):
        """Dominio ORM equivalente al filtro histórico por cuentas CXC/CXP del contacto."""
        company = self.env.company
        partner_cc = partner.with_company(company)
        rec_acc = partner_cc.property_account_receivable_id
        pay_acc = partner_cc.property_account_payable_id
        if not rec_acc or not pay_acc:
            return None
        return [
            ('partner_id', '=', partner.id),
            ('account_id', 'in', (rec_acc.id, pay_acc.id)),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_subsection', 'line_note')),
            ('company_id', 'in', self.env.companies.ids),
        ]

    def _action_open_bi_partner_ageing(self):
        """Abre el OWL unificado con Reporte de seguimiento (partner.ageing / bi_account_report)."""
        self.ensure_one()
        Report = self.env['partner.ageing']
        rec = Report.search([], limit=1, order='id desc')
        today = fields.Date.today()
        defaults = {
            'partner_ids': [(6, 0, [self.id])],
            'on_date': today,
            'account_type': 'both',
            'period_length': 30,
            'based_on': 'due',
        }
        if rec:
            rec.write({
                'partner_ids': [(6, 0, [self.id])],
                'on_date': today,
            })
        else:
            rec = Report.create(defaults)
        return rec.action_apply_filters_ageing()

    def _action_open_partner_ledger_enterprise(self):
        """Abre el Partner Ledger OWL de Accounting Reports (Enterprise)."""
        self.ensure_one()
        report = self.env.ref('account_reports.partner_ledger_report')
        options = report.get_options(previous_options={'partner_ids': [self.id]})
        action_vals = dict(self.env['ir.actions.actions']._for_xml_id(
            'account_reports.action_account_report_partner_ledger'
        ))
        action_vals['params'] = {
            'options': options,
            'ignore_session': True,
        }
        return action_vals

    def action_open_partner_ledger(self):
        """Enterprise: Partner Ledger OWL; Community: Reporte de seguimiento (bi_financial_reports_comm)."""
        self.ensure_one()
        if self._account_reports_installed():
            return self._action_open_partner_ledger_enterprise()
        return self._action_open_bi_partner_ageing()

    @api.depends_context('company')
    def _compute_journal_item_ids(self):
        for partner in self:
            if not partner.id:
                partner.journal_item_ids = self.env['account.move.line'].browse()
                continue
            domain = partner._partner_ledger_receivable_payable_domain(partner)
            if not domain:
                partner.journal_item_ids = self.env['account.move.line'].browse()
                continue
            partner.journal_item_ids = self.env['account.move.line'].search(
                domain,
                limit=self._PARTNER_LEDGER_TAB_AML_LIMIT,
                order='date desc, id desc',
            )

    def _compute_balance(self):
        for partner in self:
            partner.balance = (partner.debit or 0.0) - (partner.credit or 0.0)

    balance = fields.Monetary(
        string='Balance',
        compute='_compute_balance',
        currency_field='currency_id',
    )
    journal_item_ids = fields.One2many(
        comodel_name='account.move.line',
        inverse_name='partner_id',
        string='Journal Items',
        compute='_compute_journal_item_ids',
    )

    def action_open_partner_ledger_report(self):
        """Compatibilidad: delega en action_open_partner_ledger."""
        return self.action_open_partner_ledger()
