# -*- coding: utf-8 -*-
"""Patrones propuestos por IA → aprendizaje persistente por diario/formato → modelos CE `account.reconcile.model`."""

import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GnQifReconcileLearn(models.Model):
    _name = 'gn.qif.reconcile.learn'
    _description = 'Conciliación: patrón aprendido desde IA por banco/diario'
    _inherit = ['mail.thread']
    _order = 'last_hit_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre de la regla (IA)', required=True, tracking=True)
    active = fields.Boolean(default=True)

    journal_id = fields.Many2one(
        'account.journal', string='Diario bancario', required=True,
        ondelete='cascade', tracking=True,
        domain="[('type', '=', 'bank')]",
    )

    bank_hint = fields.Char(
        string='Banco detectado (archivo)',
        help='Valor de archivo al momento del aprendizaje (solo referencia).',
    )

    file_format_key = fields.Char(
        string='Formato archivo',
        help='Clave interna igual a file_format del importador IA (p. ej. xlsx_atlantida).',
        index=True,
    )

    match_label = fields.Selection(
        selection=[
            ('contains', 'Contains'),
            ('not_contains', 'Not Contains'),
            ('match_regex', 'Match Regex'),
        ],
        string='Tipo de etiqueta',
        required=True,
        tracking=True,
    )

    match_label_param = fields.Char(string='Parámetro de etiqueta', required=True)

    fingerprint = fields.Char(
        index=True,
        required=True,
        readonly=True,
        copy=False,
        help='Firma estable para evitar duplicados por mismo diario/regla.',
    )

    account_id = fields.Many2one(
        'account.account', string='Cuenta contrapartida',
        check_company=True, tracking=True,
    )

    account_code_snap = fields.Char(string='Código cuenta (captura IA)')

    trigger = fields.Selection(
        [('manual', 'Manual'), ('auto_reconcile', 'Automated')],
        default='manual', required=True, tracking=True,
    )

    reconcile_model_id = fields.Many2one(
        'account.reconcile.model', string='Modelo Odoo (CE)',
        readonly=True,
        tracking=True,
        help='Si existe, esta regla ya fue promovida al modelo estándar de Odoo (Community).',
    )

    hit_count = fields.Integer(default=1, tracking=True)

    qif_ai_wizard_id = fields.Integer(
        string='ID asistente (último origen)',
        help='Último qif.ai.wizard transitorio; puede no conservarse.',
        readonly=True,
    )

    last_filename = fields.Char(string='Último archivo')

    last_hit_date = fields.Datetime(
        string='Último refuerzo',
        readonly=True,
        default=fields.Datetime.now,
        help='Último análisis que consolidó este patrón.',
    )

    company_id = fields.Many2one(
        related='journal_id.company_id', store=True, readonly=True,
    )

    _unique_journal_fingerprint = models.Constraint(
        'unique(journal_id, fingerprint)',
        'Este patrón ya está registrado para el mismo diario.',
    )

    @staticmethod
    def fingerprint_for(match_label, param):
        key = '|'.join([(match_label or ''), (param or '').strip().lower()])
        return hashlib.sha256(key.encode('utf-8')).hexdigest()[:32]

    @api.model
    def ingest_from_ai(self, wizard, ai_result):
        """Persiste/refuerza reglas desde el JSON de la IA."""
        j = wizard.journal_id
        if not j:
            return (0, 0)
        data = ai_result or {}
        company = j.company_id
        new_n = dup_n = 0
        wiz_id = wizard.id if getattr(wizard, 'id', None) else False
        fm = wizard.file_format or ''
        bh = wizard.file_bank_name or ''

        for rm in data.get('reconcile_models') or []:
            name = (rm.get('name') or '').strip()
            ml = rm.get('match_label') or 'contains'
            if ml not in ('contains', 'not_contains', 'match_regex'):
                ml = 'contains'
            param = (rm.get('match_label_param') or '').strip()
            trig = rm.get('trigger') or 'manual'
            if trig not in ('manual', 'auto_reconcile'):
                trig = 'manual'
            account = self.env['account.account'].with_company(company).search(
                [('code', '=', (rm.get('account_code') or '').strip())], limit=1,
            )

            if not name or not param:
                continue

            fp = self.fingerprint_for(ml, param)
            rec = self.search([
                ('journal_id', '=', j.id),
                ('fingerprint', '=', fp),
            ], limit=1)

            vals_base = {
                'name': name[:256],
                'bank_hint': bh[:128],
                'file_format_key': fm[:64] if fm != 'unknown' else '',
                'match_label': ml,
                'match_label_param': param[:512],
                'trigger': trig,
                'account_id': account.id if account else False,
                'account_code_snap': rm.get('account_code', '') or '',
                'qif_ai_wizard_id': wiz_id,
                'last_filename': (wizard.qif_filename or '')[:256],
                'last_hit_date': fields.Datetime.now(),
            }
            if rec:
                upd = {'hit_count': (rec.hit_count or 1) + 1}
                upd.update(vals_base)
                rec.write(upd)
                dup_n += 1
            else:
                self.create(dict(vals_base, fingerprint=fp, journal_id=j.id, hit_count=1))
                new_n += 1
        return (new_n, dup_n)

    def action_open_reconcile_model(self):
        self.ensure_one()
        if not self.reconcile_model_id:
            raise UserError(_('Este patrón aún no tiene un modelo estándar de Odoo asociado.'))
        action = self.env['ir.actions.actions']._for_xml_id('account.action_account_reconcile_model')
        action = dict(action)
        action.update({
            'view_mode': 'form',
            'res_id': self.reconcile_model_id.id,
            'views': [(False, 'form')],
            'domain': [('id', '=', self.reconcile_model_id.id)],
        })
        return action

    @api.model
    def link_promoted_ce_model(self, journal, match_label, param, odoo_rec):
        if not journal or not odoo_rec:
            return
        fp = self.fingerprint_for(match_label, param)
        rec = self.search([
            ('journal_id', '=', journal.id),
            ('fingerprint', '=', fp),
            ('reconcile_model_id', '=', False),
        ], limit=1)
        if rec:
            rec.write({'reconcile_model_id': odoo_rec.id})
