# -*- coding: utf-8 -*-
import hashlib
import base64

from odoo import api, fields, models, _


class GnQifImportHistory(models.Model):
    _name = 'gn.qif.import.history'
    _description = 'Historial de importaciones QIF (IA)'
    _order = 'create_date desc'
    _check_company_auto = True

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    journal_id = fields.Many2one(
        'account.journal', string='Diario', required=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
        index=True,
    )
    filename = fields.Char(string='Archivo')
    file_hash = fields.Char(string='Huella del archivo', required=True, index=True, readonly=True)
    line_count = fields.Integer(string='Líneas a importar', readonly=True)
    lines_imported = fields.Integer(string='Líneas importadas', readonly=True)
    lines_skipped = fields.Integer(string='Líneas omitidas (duplicado)', readonly=True)
    statement_ids = fields.Many2many(
        'account.bank.statement',
        'gn_qif_history_statement_rel',
        'history_id', 'statement_id',
        string='Extractos',
        readonly=True,
    )
    attachment_id = fields.Many2one('ir.attachment', string='Adjunto QIF', readonly=True)

    _unique_journal_file_hash = models.Constraint(
        'unique (company_id, journal_id, file_hash)',
        'Este archivo QIF ya consta en el historial para este diario.',
    )

    @api.depends('filename', 'journal_id', 'create_date')
    def _compute_name(self):
        for rec in self:
            fn = rec.filename or _('QIF')
            jn = rec.journal_id.name or ''
            rec.name = f'{fn} — {jn}'

    def action_unblock(self):
        """Remove the import lock so the same QIF can be imported again."""
        self.ensure_one()
        self.unlink()
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def hash_from_datas(self, datas_b64):
        """SHA-256 del contenido binario del QIF (campo Binary en base64)."""
        if not datas_b64:
            return hashlib.sha256(b'').hexdigest()
        if isinstance(datas_b64, str):
            raw = base64.b64decode(datas_b64.encode('ascii'))
        else:
            raw = base64.b64decode(datas_b64)
        return hashlib.sha256(raw).hexdigest()
