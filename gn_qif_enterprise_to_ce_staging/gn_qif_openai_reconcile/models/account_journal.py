# -*- coding: utf-8 -*-
import hashlib

from odoo import Command, fields, models, _
from odoo.addons.base.models.res_bank import sanitize_account_number
from odoo.exceptions import UserError

from . import gn_qif_parser


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    qif_decimal_point = fields.Char(
        string='QIF: separador decimal',
        default='.',
        help='Evita errores al convertir importes en importación QIF (p. ej. coma).',
    )
    qif_date_format = fields.Selection(
        selection=[
            ('month_first', 'mm/dd/aa'),
            ('day_first', 'dd/mm/aa'),
        ],
        default='day_first',
        string='QIF: formato de fechas',
    )

    @staticmethod
    def _check_qif(raw_file):
        return (raw_file or b'').strip().startswith(b'!Type:')

    @staticmethod
    def _ensure_utf8(raw_file):
        """Re-encode QIF bytes to UTF-8 if they are in Latin-1/CP1252."""
        try:
            raw_file.decode('utf-8')
            return raw_file
        except (UnicodeDecodeError, AttributeError):
            return raw_file.decode('latin-1').encode('utf-8')

    @staticmethod
    def _compute_qif_unique_id(tx):
        """Hash estable para deduplicar importaciones (misma lógica que el asistente)."""
        ref = (tx.get('payment_ref') or '').strip().upper()
        check = tx.get('ref') or ''
        date = str(tx.get('date', ''))
        amount = tx.get('amount', 0)
        seq = tx.get('sequence', 0)
        raw = f"{date}|{amount}|{ref}|{check}|{seq}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _gn_qif_complete_bank_statement_vals(self, stmts_vals, journal, account_number, attachment):
        """Equivalente a la preparación de valores del import bancario (Community)."""
        for st_vals in stmts_vals:
            if not st_vals.get('reference'):
                st_vals['reference'] = attachment.name
                st_vals['attachment_ids'] = [Command.set(attachment.ids)]
            for line_vals in st_vals['transactions']:
                line_vals['journal_id'] = journal.id
                unique_import_id = line_vals.get('unique_import_id')
                if unique_import_id:
                    sanitized = sanitize_account_number(account_number) if account_number else ''
                    line_vals['unique_import_id'] = (
                        (sanitized + '-' if sanitized else '') + str(journal.id) + '-' + unique_import_id
                    )
                if not line_vals.get('partner_bank_id'):
                    identifying_string = line_vals.get('account_number')
                    if identifying_string:
                        if line_vals.get('partner_id'):
                            partner_bank = self.env['res.partner.bank'].search([
                                ('acc_number', '=', identifying_string),
                                ('partner_id', '=', line_vals['partner_id'])
                            ], limit=1)
                        else:
                            partner_bank = self.env['res.partner.bank'].search([
                                ('acc_number', '=', identifying_string),
                                ('company_id', 'in', (False, journal.company_id.id))
                            ], limit=2)
                        if partner_bank and len(partner_bank) == 1:
                            line_vals['partner_bank_id'] = partner_bank.id
                            line_vals['partner_id'] = partner_bank.partner_id.id
        return stmts_vals

    def _gn_qif_create_bank_statements(self, stmts_vals, raise_no_imported_file=True):
        """Crea extractos; omite transacciones ya importadas (unique_import_id)."""
        BankStatement = self.env['account.bank.statement']
        BankStatementLine = self.env['account.bank.statement.line']

        statement_ids = []
        statement_line_ids = []
        ignored_qty = 0
        for st_vals in stmts_vals:
            filtered_st_lines = []
            for line_vals in st_vals['transactions']:
                uid = line_vals.get('unique_import_id')
                dup = bool(
                    uid
                    and BankStatementLine.sudo().search(
                        [('unique_import_id', '=', uid)], limit=1,
                    )
                )
                if (line_vals.get('amount', 0) != 0
                        and (not uid or not dup)):
                    filtered_st_lines.append(line_vals)
                else:
                    ignored_qty += 1
                    if st_vals.get('balance_start') is not None:
                        st_vals['balance_start'] = st_vals.get('balance_start', 0) + float(
                            line_vals.get('amount', 0))

            if filtered_st_lines:
                st_block = {k: v for k, v in st_vals.items() if k != 'transactions'}
                st_block['line_ids'] = [Command.create(line) for line in filtered_st_lines]
                statement = BankStatement.with_context(
                    default_journal_id=self.id,
                    auto_statement_processing=True,
                ).create(st_block)
                if not statement.name:
                    statement.name = st_block.get('reference', '')
                statement_ids.append(statement.id)
                statement_line_ids.extend(statement.line_ids.ids)

        if not statement_line_ids and raise_no_imported_file:
            raise UserError(_('Ya se había importado este archivo: no quedan líneas nuevas.'))
        return statement_ids, ignored_qty

    def _parse_bank_statement_file(self, raw_file):
        """API tipo import: solo QIF (Community no incluye el motor genérico Enterprise)."""
        if not self._check_qif(raw_file):
            raise UserError(
                _('El archivo no es un QIF reconocido. Use el asistente «Análisis QIF con IA» o un archivo QIF.'))
        raw = self._ensure_utf8(raw_file)
        transactions, _meta = gn_qif_parser.parse_qif_bytes(self, raw)
        for tx in transactions:
            if not tx.get('unique_import_id'):
                tx['unique_import_id'] = self._compute_qif_unique_id(tx)
        total = sum(t.get('amount', 0) for t in transactions)
        vals_bank_statement = {
            'balance_end_real': total,
            'transactions': transactions,
        }
        return [[None, None, [vals_bank_statement]]]
