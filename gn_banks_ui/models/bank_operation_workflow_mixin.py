# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_DOCUMENT_NUMBER_SUFFIX_RE = re.compile(
    r'([A-Z]{2,}(?:/[A-Z0-9._-]+)+)\s*$',
    re.IGNORECASE,
)

OPERATION_TYPE_META = {
    'debit': {'css': 'debit', 'icon': 'fa-arrow-circle-up'},
    'credit': {'css': 'credit', 'icon': 'fa-arrow-circle-down'},
    'deposit': {'css': 'deposit', 'icon': 'fa-university'},
    'credit_card': {'css': 'pos', 'icon': 'fa-credit-card'},
    'check': {'css': 'check', 'icon': 'fa-money'},
    'transference': {'css': 'transfer', 'icon': 'fa-exchange'},
    'transference_banks': {'css': 'interbank', 'icon': 'fa-random'},
}


class BankOperationWorkflowMixin(models.AbstractModel):
    _name = 'bank.operation.workflow.mixin'
    _description = 'Capa de flujo de trabajo UI para operaciones bancarias'

    workflow_state = fields.Selection(
        selection='_selection_workflow_state',
        string='Estado del flujo',
        default='draft',
        copy=False,
        tracking=True,
        index=True,
    )
    approval_required = fields.Boolean(
        string='Requiere aprobación',
        compute='_compute_approval_required',
    )
    submitted_by = fields.Many2one('res.users', string='Enviado por', copy=False, readonly=True)
    submitted_date = fields.Datetime(string='Fecha de envío', copy=False, readonly=True)
    approved_by = fields.Many2one('res.users', string='Aprobado por', copy=False, readonly=True)
    approved_date = fields.Datetime(string='Fecha de aprobación', copy=False, readonly=True)
    validated_by = fields.Many2one('res.users', string='Validado por', copy=False, readonly=True)
    validated_date = fields.Datetime(string='Fecha de validación', copy=False, readonly=True)
    reconciliation_status = fields.Selection(
        selection='_selection_reconciliation_status',
        string='Estado de conciliación',
        compute='_compute_reconciliation_status',
        store=True,
    )
    ui_partner_id = fields.Many2one(
        'res.partner',
        string='Contacto principal',
        compute='_compute_ui_partner_id',
    )
    ui_operation_type_key = fields.Char(compute='_compute_ui_operation_meta', store=True)
    ui_operation_type_label = fields.Char(compute='_compute_ui_operation_meta', store=True)
    ui_operation_icon = fields.Char(compute='_compute_ui_operation_meta', store=True)
    attachment_count = fields.Integer(compute='_compute_attachment_counts')
    document_count = fields.Integer(compute='_compute_attachment_counts')
    invoice_count = fields.Integer(compute='_compute_attachment_counts')
    message_count = fields.Integer(compute='_compute_attachment_counts')
    ui_document_number = fields.Char(
        string='Número de documento',
        compute='_compute_ui_document_number',
    )

    # ------------------------------------------------------------------ helpers
    @api.model
    def _selection_workflow_state(self):
        return [
            ('draft', _('Borrador')),
            ('pending_approval', _('Pendiente aprobación')),
            ('approved', _('Aprobado')),
            ('validated', _('Validado')),
            ('posted', _('Validado')),
            ('reconciled', _('Validado')),
            ('cancelled', _('Cancelado')),
        ]

    @api.model
    def _selection_reconciliation_status(self):
        return [
            ('none', _('Sin conciliar')),
            ('partial', _('Parcialmente conciliado')),
            ('full', _('Totalmente conciliado')),
        ]

    @api.model
    def _bank_ui_operation_type_labels(self):
        return {
            'debit': _('Débito'),
            'credit': _('Crédito'),
            'deposit': _('Depósito'),
            'credit_card': _('Liquidación POS'),
            'check': _('Cheque'),
            'transference': _('Transferencia'),
            'transference_banks': _('Transferencia interbancaria'),
        }
    @api.model
    def _bank_ui_is_document_number(self, value):
        text = (value or '').strip()
        if not text or text == '/':
            return False
        if len(text) > 64 or ',' in text:
            return False
        return '/' in text

    @api.model
    def _bank_ui_extract_document_number(self, value):
        text = (value or '').strip()
        if not text or text == '/':
            return False
        if self._bank_ui_is_document_number(text):
            return text
        match = _DOCUMENT_NUMBER_SUFFIX_RE.search(text)
        if match:
            seq = match.group(1).strip()
            if self._bank_ui_is_document_number(seq):
                return seq
        return False

    def _bank_ui_sequence_preview_name(self):
        self.ensure_one()
        if not hasattr(self, '_get_sequence'):
            return False
        if not self.journal_id or not getattr(self, 'move_type', None):
            return False
        sequence = self._get_sequence()
        if not sequence:
            return False
        return sequence.get_next_char(sequence.number_next_actual)

    def _bank_ui_resolve_document_number(self):
        self.ensure_one()
        name = (self.name or '').strip()
        dummy = (getattr(self, 'dummy_name', None) or '').strip()
        preview = (self._bank_ui_sequence_preview_name() or '').strip()

        extracted = self._bank_ui_extract_document_number(name)
        if extracted:
            return extracted

        for candidate in (dummy, preview):
            if candidate and candidate != '/' and self._bank_ui_is_document_number(candidate):
                return candidate
        return '/'

    @api.depends('name', 'dummy_name', 'journal_id', 'move_type', 'state')
    def _compute_ui_document_number(self):
        for rec in self:
            rec.ui_document_number = rec._bank_ui_resolve_document_number()

    def _bank_ui_move_type(self):
        self.ensure_one()
        return getattr(self, 'move_type', False) or self._name

    def _bank_ui_operation_meta(self):
        self.ensure_one()
        key = self._bank_ui_move_type()
        meta = OPERATION_TYPE_META.get(key, {
            'css': 'transfer',
            'icon': 'fa-bank',
        })
        labels = self._bank_ui_operation_type_labels()
        fallback = key.replace('_', ' ').title() if key else _('Operación bancaria')
        return {
            'label': labels.get(key, fallback),
            'css': meta.get('css', 'transfer'),
            'icon': meta.get('icon', 'fa-bank'),
        }

    def _bank_ui_get_partner_record(self):
        self.ensure_one()
        if getattr(self, 'partner_id', False):
            return self.partner_id
        lines = getattr(self, 'debit_line_ids', False) or getattr(self, 'check_lines', False)
        if lines:
            partner_lines = lines.filtered('partner_id')
            if partner_lines:
                return partner_lines[0].partner_id
        return False

    def _bank_ui_reconcilable_lines(self):
        self.ensure_one()
        move = getattr(self, 'move_id', False)
        if not move or move.state != 'posted':
            return self.env['account.move.line']
        return move.line_ids.filtered(
            lambda l: l.account_id.reconcile and not l.display_type
        )

    def _bank_ui_get_reconciliation_status(self):
        self.ensure_one()
        lines = self._bank_ui_reconcilable_lines()
        if not lines:
            return 'none'
        reconciled = lines.filtered('reconciled')
        if not reconciled:
            return 'none'
        if len(reconciled) == len(lines):
            return 'full'
        return 'partial'

    def _bank_ui_sync_workflow_state(self):
        for rec in self:
            if rec.state == 'cancel':
                rec.workflow_state = 'cancelled'
                continue
            if rec.state == 'draft':
                if rec.workflow_state not in ('pending_approval', 'approved'):
                    rec.workflow_state = 'draft'
                continue
            if rec.state == 'validated':
                recon = rec._bank_ui_get_reconciliation_status()
                if recon == 'full':
                    rec.workflow_state = 'reconciled'
                elif rec.move_id and rec.move_id.state == 'posted':
                    rec.workflow_state = 'posted'
                else:
                    rec.workflow_state = 'validated'

    def _bank_ui_check_approval_before_validate(self):
        for rec in self:
            if not rec.approval_required:
                continue
            if rec.workflow_state not in ('approved',):
                if rec.workflow_state == 'pending_approval':
                    raise UserError(_(
                        'La operación «%s» está pendiente de aprobación. Apruébela antes de validar.',
                        rec.display_name,
                    ))
                raise UserError(_(
                    'La operación «%s» requiere aprobación. Envíela y obtenga la aprobación antes de validar.',
                    rec.display_name,
                ))

    def _bank_ui_after_validate(self):
        now = fields.Datetime.now()
        user = self.env.user
        for rec in self:
            rec.write({
                'validated_by': user.id,
                'validated_date': now,
            })
            rec._bank_ui_sync_workflow_state()

    def _bank_ui_after_cancel(self):
        for rec in self:
            rec.workflow_state = 'cancelled'

    def _bank_ui_after_set_draft(self):
        for rec in self:
            rec.write({
                'workflow_state': 'draft',
                'submitted_by': False,
                'submitted_date': False,
                'approved_by': False,
                'approved_date': False,
                'validated_by': False,
                'validated_date': False,
            })

    # ------------------------------------------------------------------ computes
    @api.depends('company_id', 'company_id.banks_require_approval')
    def _compute_approval_required(self):
        for rec in self:
            company = getattr(rec, 'company_id', False)
            rec.approval_required = bool(company and company.banks_require_approval)

    @api.depends('move_id', 'move_id.state', 'move_id.line_ids.reconciled', 'move_id.line_ids.account_id.reconcile')
    def _compute_reconciliation_status(self):
        for rec in self:
            rec.reconciliation_status = rec._bank_ui_get_reconciliation_status()

    def _compute_ui_partner_id(self):
        for rec in self:
            rec.ui_partner_id = rec._bank_ui_get_partner_record()

    @api.depends('move_type')
    def _compute_ui_operation_meta(self):
        for rec in self:
            meta = rec._bank_ui_operation_meta()
            rec.ui_operation_type_key = meta['css']
            rec.ui_operation_type_label = meta['label']
            rec.ui_operation_icon = meta['icon']

    def _compute_attachment_counts(self):
        for rec in self:
            rec.attachment_count = len(rec.message_ids.mapped('attachment_ids'))
            docs = getattr(rec, 'document_ids', self.env['bank.documents'])
            rec.document_count = len(docs)
            invoice = getattr(rec, 'bank_invoice_id', False)
            rec.invoice_count = 1 if invoice else 0
            rec.message_count = len(rec.message_ids)

    # ------------------------------------------------------------------ workflow actions
    def action_submit_for_approval(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.approval_required:
                raise UserError(_('No se requiere aprobación para esta compañía.'))
            rec.write({
                'workflow_state': 'pending_approval',
                'submitted_by': self.env.user.id,
                'submitted_date': fields.Datetime.now(),
            })
        return True

    def action_approve(self):
        for rec in self.filtered(lambda r: r.workflow_state == 'pending_approval'):
            rec.write({
                'workflow_state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
        return True

    def action_reject_approval(self):
        for rec in self.filtered(lambda r: r.workflow_state == 'pending_approval'):
            rec.write({
                'workflow_state': 'draft',
                'submitted_by': False,
                'submitted_date': False,
            })
        return True

    # ------------------------------------------------------------------ stat button actions
    def action_view_account_move(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asiento contable'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }

    def action_view_attachments(self):
        self.ensure_one()
        attachment_ids = self.message_ids.mapped('attachment_ids').ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Adjuntos'),
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', attachment_ids)],
        }

    def action_view_documents(self):
        self.ensure_one()
        if not getattr(self, 'document_ids', False):
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documentos'),
            'res_model': 'bank.documents',
            'view_mode': 'list,form',
            'domain': [('bank_debit_id', '=', self.id)],
        }

    def action_view_bank_invoice(self):
        self.ensure_one()
        if hasattr(self, 'action_open_bank_invoice'):
            return self.action_open_bank_invoice()
        if not getattr(self, 'bank_invoice_id', False):
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura relacionada'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.bank_invoice_id.id,
        }

    def action_view_reconciliation(self):
        self.ensure_one()
        if not self.move_id:
            return False
        lines = self._bank_ui_reconcilable_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Conciliación'),
            'res_model': 'account.move.line',
            'view_mode': 'list',
            'domain': [('id', 'in', lines.ids)],
            'context': {'search_default_unreconciled': 1},
        }

    def action_view_template(self):
        self.ensure_one()
        if not getattr(self, 'template_id', False):
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Plantilla'),
            'res_model': 'bank.template',
            'view_mode': 'form',
            'res_id': self.template_id.id,
        }

    def get_bank_timeline_events(self):
        """Return timeline events for OWL widget."""
        self.ensure_one()
        events = []
        if self.create_date:
            events.append({
                'kind': 'created',
                'label': _('Creado'),
                'date': fields.Datetime.to_string(self.create_date),
                'user': self.create_uid.name if self.create_uid else '',
                'description': _('Documento creado'),
                'icon': 'fa-plus-circle',
            })
        if self.submitted_date:
            events.append({
                'kind': 'submitted',
                'label': _('Enviado a aprobación'),
                'date': fields.Datetime.to_string(self.submitted_date),
                'user': self.submitted_by.name if self.submitted_by else '',
                'description': _('Enviado a aprobación de tesorería'),
                'icon': 'fa-paper-plane',
            })
        if self.approved_date:
            events.append({
                'kind': 'approved',
                'label': _('Aprobado'),
                'date': fields.Datetime.to_string(self.approved_date),
                'user': self.approved_by.name if self.approved_by else '',
                'description': _('Aprobado por tesorería'),
                'icon': 'fa-check-circle',
            })
        if self.validated_date:
            events.append({
                'kind': 'validated',
                'label': _('Validado'),
                'date': fields.Datetime.to_string(self.validated_date),
                'user': self.validated_by.name if self.validated_by else '',
                'description': _('Operación validada'),
                'icon': 'fa-check',
            })
        if self.move_id:
            events.append({
                'kind': 'move',
                'label': _('Asiento contable'),
                'date': fields.Datetime.to_string(self.move_id.create_date) if self.move_id.create_date else '',
                'user': self.move_id.create_uid.name if self.move_id.create_uid else '',
                'description': self.move_id.name or _('Asiento contable generado'),
                'icon': 'fa-book',
            })
        if self.reconciliation_status == 'full':
            events.append({
                'kind': 'reconciled',
                'label': _('Conciliado'),
                'date': fields.Datetime.to_string(self.write_date),
                'user': '',
                'description': _('Líneas bancarias totalmente conciliadas'),
                'icon': 'fa-link',
            })
        if self.state == 'cancel':
            events.append({
                'kind': 'cancelled',
                'label': _('Cancelado'),
                'date': fields.Datetime.to_string(self.write_date),
                'user': self.write_uid.name if self.write_uid else '',
                'description': _('Operación cancelada'),
                'icon': 'fa-times-circle',
            })
        events.sort(key=lambda e: e.get('date') or '')
        return events
