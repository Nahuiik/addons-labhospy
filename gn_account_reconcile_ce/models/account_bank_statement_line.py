# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, exceptions, models

from .gn_reconcile_matching import GnCeMatchingScorer


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    @api.model
    def gn_ce_get_matching_candidates_for_line(self, statement_line_id: int, candidate_limit: int = 64):
        """Candidatos `account.move.line` ordenados por pipeline Nahuiik (JSON)."""
        st = self.browse(int(statement_line_id))
        st.ensure_one()
        if st.company_id not in self.env.companies:
            raise exceptions.AccessError(_('No tiene permiso para esta compañía.'))
        if st.is_reconciled:
            return {'line': st.gn_ce_workspace_line_payload(), 'candidates': []}

        tol = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'gn_account_reconcile_ce.amount_tolerance',
                '0.01',
            )
        )
        icp_window = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'gn_account_reconcile_ce.date_window_days',
                '150',
            )
        )
        search_cap = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'gn_account_reconcile_ce.candidate_search_cap',
                '450',
            )
        )

        scorer = GnCeMatchingScorer(st.currency_id, tol)

        domain = st._get_default_amls_matching_domain()
        if st.date:
            domain += [
                ('date', '>=', st.date - timedelta(days=icp_window)),
                ('date', '<=', st.date + timedelta(days=icp_window)),
            ]

        AM = self.env['account.move.line'].with_company(st.company_id)
        amls = AM.search(domain, limit=search_cap, order='date desc, id desc')

        st_blobs = []
        for fld in ('payment_ref', 'narration', 'ref', 'partner_name'):
            val = getattr(st, fld, '') or ''
            if val:
                st_blobs.append(str(val))

        amt_res = float(st.amount_residual or 0.0)
        aml_fields = [
            'id',
            'name',
            'ref',
            'date',
            'amount_residual',
            'amount_residual_currency',
            'partner_id',
            'currency_id',
            'account_id',
            'move_id',
        ]
        scored = []
        for row in amls.read(aml_fields):
            amt_key = (
                'amount_residual_currency'
                if (
                    st.foreign_currency_id
                    and row.get('currency_id')
                    and row['currency_id'][0] == st.foreign_currency_id.id
                )
                else 'amount_residual'
            )
            composite, detail = scorer.compose(
                st_partner_id=st.partner_id.id if st.partner_id else False,
                st_amount_residual=amt_res,
                st_date=st.date,
                st_blobs=st_blobs,
                aml=dict(row),
                amount_compare_field=amt_key,
            )
            detail['move_line_id'] = row['id']
            detail['partner'] = row['partner_id'][1] if row.get('partner_id') else ''
            detail['label'] = row.get('name') or ''
            detail['date'] = str(row.get('date') or '')
            detail['amount_residual'] = float(row.get('amount_residual') or 0.0)
            detail['move_display'] = (
                row['move_id'][1]
                if isinstance(row.get('move_id'), (list, tuple)) and len(row['move_id']) > 1
                else ''
            )
            scored.append((composite, detail))

        scored.sort(key=lambda t: t[0], reverse=True)
        cap = max(4, min(int(candidate_limit), 240))
        top = [det for _c, det in scored[:cap]]
        return {'line': st.gn_ce_workspace_line_payload(), 'candidates': top}

    def gn_ce_workspace_line_payload(self):
        self.ensure_one()
        liq, susp, _other = self._seek_for_lines()
        return {
            'id': self.id,
            'date': str(self.date),
            'journal_id': self.journal_id.id,
            'payment_ref': self.payment_ref or '',
            'partner_name': self.partner_name or '',
            'partner_id': self.partner_id.id if self.partner_id else False,
            'amount': float(self.amount or 0.0),
            'amount_residual': float(self.amount_residual or 0.0),
            'currency': self.currency_id.name,
            'liquidity_line_ids': liq.ids,
            'suspense_line_ids': susp.ids,
            'is_reconciled': bool(self.is_reconciled),
            'checked': bool(getattr(self, 'checked', False)),
        }

    @api.model
    def gn_ce_list_unreconciled_lines(self, journal_id: int, offset: int = 0, page_size: int = 40):
        """Listado paginado para lista virtualizada (OWL)."""
        journal = self.env['account.journal'].browse(int(journal_id))
        if not journal:
            raise exceptions.UserError(_('Diario inválido.'))
        if journal.company_id not in self.env.companies:
            raise exceptions.AccessError(_('No tiene permiso para esta compañía.'))
        dom = [
            ('journal_id', '=', journal.id),
            ('is_reconciled', '=', False),
        ]
        page = max(1, int(page_size))
        off = max(0, int(offset))
        lines = self.search(dom, limit=page + 1, offset=off, order='internal_index desc')
        has_more = len(lines) > page
        slice_lines = lines[:page]
        next_off = off + len(slice_lines)
        return {
            'items': [ln.gn_ce_workspace_line_payload() for ln in slice_lines],
            'has_more': has_more,
            'offset': off,
            'next_offset': next_off,
            'page_size': page,
        }

    @api.model
    def gn_ce_reconcile_line_with_aml(self, statement_line_id: int, move_line_id: int):
        """Suspense CE + `reconcile()` entre contraparte y línea objetivo."""
        st = self.browse(int(statement_line_id))
        st.ensure_one()
        if st.company_id not in self.env.companies:
            raise exceptions.AccessError(_('Sin acceso compañía.'))
        if st.is_reconciled:
            raise exceptions.UserError(_('La línea ya está conciliada.'))
        aml = self.env['account.move.line'].browse(int(move_line_id)).exists()
        if not aml:
            raise exceptions.UserError(_('La contrapartida no existe.'))
        if aml.reconciled:
            raise exceptions.UserError(_('La contrapartida ya está reconciliada.'))
        if aml.company_id.root_id != st.company_id.root_id:
            raise exceptions.UserError(_('Multicompañía incompatible.'))

        _liquidity_lines, suspense_lines, other_lines = st._seek_for_lines()
        if len(suspense_lines) != 1:
            raise exceptions.UserError(
                _('Extracto inconsistente: se espera una línea de suspensión (hay %s).')
                % len(suspense_lines),
            )

        if other_lines:
            other_lines.with_context(skip_account_move_synchronization=True).unlink()

        suspense_lines.with_context(skip_account_move_synchronization=True).write({
            'account_id': aml.account_id.id,
        })
        (suspense_lines + aml).reconcile()
        return {'ok': True, 'line': st.gn_ce_workspace_line_payload()}

    @api.model
    def gn_ce_try_zero_click(self, statement_line_id: int, min_score: float | None = None):
        IC = self.env['ir.config_parameter'].sudo()
        if min_score is None:
            min_score = float(IC.get_param('gn_account_reconcile_ce.auto_accept_score', '93'))
        st = self.browse(int(statement_line_id))
        if not st or st.is_reconciled:
            return {'applied': False}
        payload = self.gn_ce_get_matching_candidates_for_line(st.id, candidate_limit=8)
        cands = payload.get('candidates') or []
        if not cands:
            return {'applied': False}
        top = float(cands[0].get('composite') or 0.0)
        if top < float(min_score):
            return {'applied': False, 'best_score': top}
        ml_id = cands[0]['move_line_id']
        return {'applied': True, 'payload': self.gn_ce_reconcile_line_with_aml(st.id, ml_id)}

    @api.model
    def gn_ce_default_params(self):
        IC = self.env['ir.config_parameter'].sudo()
        return {
            'amount_tolerance': float(IC.get_param('gn_account_reconcile_ce.amount_tolerance', '0.01')),
            'date_window_days': int(IC.get_param('gn_account_reconcile_ce.date_window_days', '150')),
            'auto_accept_score': float(IC.get_param('gn_account_reconcile_ce.auto_accept_score', '93')),
        }
