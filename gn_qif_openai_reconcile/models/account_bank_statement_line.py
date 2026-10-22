# -*- coding: utf-8 -*-
"""Extensión de líneas extracto para import Nahuiik y utilidades reconciliación CE."""
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    unique_import_id = fields.Char(
        string='ID importación', readonly=True, copy=False, index='btree_not_null',
    )

    _gn_qif_openai_line_unique = models.Constraint(
        'unique (unique_import_id)',
        "Una transacción con este identificador de importación ya existe.",
    )

    def _gn_qif_label_blob(self):
        self.ensure_one()
        parts = []
        for fname in ('payment_ref', 'narration', 'ref'):
            val = getattr(self, fname, None)
            if val:
                parts.append(str(val))
        tx = getattr(self, 'transaction_type', None)
        if tx:
            parts.append(str(tx))
        return ' '.join(parts).strip().lower()

    @api.model
    def _gn_qif_rule_matches_blob(self, match_label, match_label_param, blob):
        if not match_label or not match_label_param:
            return True
        needle = match_label_param.strip()
        hay = blob or ''
        if match_label == 'contains':
            return needle.lower() in hay
        if match_label == 'not_contains':
            return needle.lower() not in hay
        if match_label == 'match_regex':
            try:
                return bool(re.search(needle, hay, re.I))
            except re.error:
                return False
        return True

    @api.model
    def _gn_qif_model_partner_ok(self, line, model):
        if model.match_partner_ids:
            partner = line.partner_id
            if not partner:
                return False
            return partner in model.match_partner_ids
        return True

    @api.model
    def _gn_qif_model_amount_ok(self, line, model):
        if not model.match_amount:
            return True
        amt = float(line.amount or 0.0)
        amin = float(model.match_amount_min or 0.0)
        amax = float(model.match_amount_max or 0.0)
        if model.match_amount == 'lower':
            return amt <= amin
        if model.match_amount == 'greater':
            return amt >= amin
        if model.match_amount == 'between':
            return amin <= amt <= max(amax, amin)
        return True

    @api.model
    def _gn_qif_model_journal_ok(self, journal, model):
        if model.match_journal_ids and journal:
            return journal in model.match_journal_ids
        return True

    @api.model
    def gn_qif_action_reconcile_model_candidates(self, statement_line_ids):
        """Devuelve acción lista de modelos CE priorizados (patrones IA + filtros modelo)."""
        lines = self.browse(statement_line_ids or [])
        if not lines:
            raise UserError(_('Selecciona al menos una línea de extracto.'))
        if len(lines.mapped('company_id')) != 1:
            raise UserError(_('Selecciona líneas de una sola compañía para listar candidatos.'))

        cid = lines[0].company_id.id
        Learn = self.env['gn.qif.reconcile.learn'].with_company(lines[0].company_id)
        Rec = self.env['account.reconcile.model'].with_company(lines[0].company_id).search([
            ('company_id', '=', cid),
            ('active', '=', True),
        ])

        ordered_ids = []
        collected = set()

        def append_model(model_rec):
            if model_rec.id not in collected:
                collected.add(model_rec.id)
                ordered_ids.append(model_rec.id)

        for line in lines:
            blob = line._gn_qif_label_blob()
            journal = line.journal_id
            learns = Learn.search([
                ('journal_id', '=', journal.id),
                ('active', '=', True),
                ('reconcile_model_id', '!=', False),
            ])
            for ln in learns:
                if self._gn_qif_rule_matches_blob(ln.match_label, ln.match_label_param, blob):
                    rm = ln.reconcile_model_id
                    if rm and rm.active:
                        append_model(rm)

        for line in lines:
            blob = line._gn_qif_label_blob()
            journal = line.journal_id
            for model in Rec.sorted(lambda m: (-int(m.sequence or 0), m.id)):
                if model.id in collected:
                    continue
                if not self._gn_qif_model_journal_ok(journal, model):
                    continue
                if not self._gn_qif_model_partner_ok(line, model):
                    continue
                if not self._gn_qif_model_amount_ok(line, model):
                    continue
                if not self._gn_qif_rule_matches_blob(model.match_label, model.match_label_param, blob):
                    continue
                append_model(model)

        # Modelos válidos sólo por diario (lista amplia cuando el filtro de texto no coincide)
        for line in lines:
            journal = line.journal_id
            for model in Rec.sorted(lambda m: (-int(m.sequence or 0), m.id)):
                if model.id in collected:
                    continue
                if not self._gn_qif_model_journal_ok(journal, model):
                    continue
                append_model(model)

        raw_action = dict(self.env['ir.actions.act_window']._for_xml_id('account.action_account_reconcile_model'))
        ctx = raw_action.get('context') or {}
        if isinstance(ctx, str):
            from ast import literal_eval

            try:
                ctx = literal_eval(ctx.strip())
            except (ValueError, SyntaxError):
                ctx = {}
        if not isinstance(ctx, dict):
            ctx = {}
        ctx.setdefault('search_default_active', True)
        name = _('Modelos reconciliación sugeridos')
        dom = [('id', 'in', ordered_ids)] if ordered_ids else [('id', '=', False)]
        raw_action.update({
            'name': name,
            'domain': dom,
            'context': ctx,
        })
        return raw_action

    @api.model
    def gn_qif_action_open_template_wizard(self, statement_line_ids=None):
        """Abre wizard de plantillas usando el mismo diario de las líneas seleccionadas."""
        lines = self.browse(statement_line_ids or [])
        if not lines:
            raise UserError(_('Selecciona al menos una línea para vincular el diario.'))
        journals = lines.mapped('journal_id')
        if len(journals) != 1:
            raise UserError(_('Selecciona líneas de un mismo diario bancario.'))
        j = journals[0]
        cmp = lines[:1].company_id
        if j.company_id.id != cmp.id:
            raise UserError(_('Inconsistencia compañía / diario.'))
        return dict(
            type='ir.actions.act_window',
            name=_('Plantillas modelo conciliación'),
            res_model='gn.qif.reconcile.template.wizard',
            view_mode='form',
            views=[(False, 'form')],
            target='new',
            context={
                'default_journal_id': j.id,
                'default_company_id': j.company_id.id,
            },
        )
