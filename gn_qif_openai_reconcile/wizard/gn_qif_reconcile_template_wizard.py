# -*- coding: utf-8 -*-
"""Plantillas funcionales tipo «uso común» sobre `account.reconcile.model` (Odoo CE)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command


class GnQifReconcileTemplateWizard(models.TransientModel):
    _name = 'gn.qif.reconcile.template.wizard'
    _description = 'Plantillas modelo de conciliación (Nahuiik + CE)'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        readonly=True,
        default=lambda s: s.env.company,
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario bancario',
        required=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'bank')]",
    )

    skip_existing_names = fields.Boolean(string='Saltar si el nombre ya existe', default=True)

    transfer_clearing_account_id = fields.Many2one(
        'account.account',
        string='Transferencias: cuenta de tránsito / contra-banco',
        required=True,
        check_company=True,
    )
    fees_expense_account_id = fields.Many2one(
        'account.account',
        string='Comisiones y cargos del banco (gasto)',
        required=True,
        check_company=True,
    )
    principal_for_split_account_id = fields.Many2one(
        'account.account',
        string='Operaciones mixtas: contrapartida principal',
        required=True,
        check_company=True,
        help='Contrapartida mayoritaria en el modelo de dos líneas (principal más porción comisión estimada).',
    )
    owner_draw_account_id = fields.Many2one(
        'account.account',
        string='Titular / retiros cuenta personal',
        required=True,
        check_company=True,
    )

    commission_contains = fields.Char(
        string='Texto etiqueta típico (comisión)',
        default='COMISION',
        help='Criterio «contiene» insensible a mayúsculas para el modelo de cargos típicos de banco.',
    )

    split_principal_percent = fields.Integer(
        string='Porcentaje principal del extracto',
        default=97,
        help='Entre 60 y 99. El complemento hasta 100% se contabiliza en la segunda línea (comisión).',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx_journal = self.env.context.get('default_journal_id')
        if ctx_journal and 'journal_id' in fields_list and not res.get('journal_id'):
            res['journal_id'] = ctx_journal
        ctx_company = self.env.context.get('default_company_id')
        if ctx_company and 'company_id' in fields_list:
            res.setdefault('company_id', ctx_company)
        return res

    @api.onchange('journal_id')
    def _onchange_journal_company(self):
        self.company_id = self.journal_id.company_id if self.journal_id else self.env.company

    @api.constrains('split_principal_percent')
    def _chk_split_principal(self):
        for w in self:
            p = int(w.split_principal_percent or 0)
            if not (60 <= p <= 99):
                raise UserError(_('El porcentaje principal debe estar entre 60 y 99.'))

    def _journal_command(self):
        self.ensure_one()
        return [Command.set([self.journal_id.id])]

    def _create_if_needed(self, Rec, vals):
        """Crea modelo de reconciliación con nombre estable o lo omite si ya existe igual."""
        self.ensure_one()
        vals_local = dict(vals)
        nm = (vals_local.pop('name', '') or '')[:256]
        if not nm:
            return Rec.browse()
        if self.skip_existing_names and Rec.search([
            ('company_id', '=', self.company_id.id),
            ('name', '=', nm),
        ], limit=1):
            return Rec.browse()
        return Rec.create(dict(vals_local, name=nm))

    def action_apply_templates(self):
        """Crea (o omite si existen los nombres) cuatro presets manuales vinculados al diario."""
        self.ensure_one()
        journal = self.journal_id
        if journal.company_id != self.company_id:
            raise UserError(_('La compañía del diario no coincide con la compañía del asistente.'))

        Rec = self.env['account.reconcile.model'].with_company(self.company_id)
        created = Rec.browse()
        pct_main = max(60, min(99, int(self.split_principal_percent or 97)))
        pct_fee = 100 - pct_main
        com_token = (self.commission_contains or 'COMISION').strip()[:512] or 'COMISION'

        base = {'trigger': 'manual', 'gn_creation_source': 'wizard_template'}
        jid = self._journal_command()

        t1_vals = dict(
            base,
            name='[Plantilla GN] Transferencias internas',
            match_journal_ids=jid,
            line_ids=[
                Command.create({
                    'sequence': 10,
                    'account_id': self.transfer_clearing_account_id.id,
                    'amount_type': 'percentage',
                    'amount_string': '100',
                    'label': _('Transferencia entre cuentas corporativas'),
                }),
            ],
        )
        m1 = self._create_if_needed(Rec, t1_vals)
        if m1:
            created |= m1

        t2_vals = dict(
            base,
            name='[Plantilla GN] Comisiones y cargos del banco',
            match_journal_ids=jid,
            match_label='contains',
            match_label_param=com_token[:512],
            line_ids=[
                Command.create({
                    'sequence': 10,
                    'account_id': self.fees_expense_account_id.id,
                    'amount_type': 'percentage',
                    'amount_string': '100',
                    'label': _('Comisión / cargo del banco'),
                }),
            ],
        )
        m2 = self._create_if_needed(Rec, t2_vals)
        if m2:
            created |= m2

        t3_vals = dict(
            base,
            name='[Plantilla GN] Movimiento principal con porción de comisión estimada',
            match_journal_ids=jid,
            line_ids=[
                Command.create({
                    'sequence': 10,
                    'account_id': self.principal_for_split_account_id.id,
                    'amount_type': 'percentage_st_line',
                    'amount_string': str(pct_main),
                    'label': _('Parte operación principal (ajuste fino habitual)'),
                }),
                Command.create({
                    'sequence': 20,
                    'account_id': self.fees_expense_account_id.id,
                    'amount_type': 'percentage_st_line',
                    'amount_string': str(pct_fee),
                    'label': _('Parte cargos / diferencial (placeholder)'),
                }),
            ],
        )
        m3 = self._create_if_needed(Rec, t3_vals)
        if m3:
            created |= m3

        t4_vals = dict(
            base,
            name='[Plantilla GN] Cuenta personal del titular',
            match_journal_ids=jid,
            line_ids=[
                Command.create({
                    'sequence': 10,
                    'account_id': self.owner_draw_account_id.id,
                    'amount_type': 'percentage',
                    'amount_string': '100',
                    'label': _('Cuenta corriente titular'),
                }),
            ],
        )
        m4 = self._create_if_needed(Rec, t4_vals)
        if m4:
            created |= m4

        action = dict(self.env['ir.actions.act_window']._for_xml_id('account.action_account_reconcile_model'))
        dom = [('match_journal_ids', 'in', [journal.id])]
        if created:
            dom = [('id', 'in', sorted(created.ids))]
        names = _('Modelos reconciliación (preset Nahuiik – %s)') % journal.name
        raw_ctx = action.get('context') or {}
        if isinstance(raw_ctx, str):
            from ast import literal_eval
            try:
                raw_ctx = literal_eval(raw_ctx.strip())
            except (ValueError, SyntaxError):
                raw_ctx = {}
        if not isinstance(raw_ctx, dict):
            raw_ctx = {}
        raw_ctx.setdefault('search_default_active', True)
        action.update({'name': names, 'domain': dom, 'context': raw_ctx})
        return action
