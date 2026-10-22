# Copyright 2015 Odoo S. A.
# Copyright 2015 Laurent Mignon <laurent.mignon@acsone.eu>
# Copyright 2015 Ronald Portier <rportier@therp.nl>
# Copyright 2016-2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import hashlib

import dateutil.parser

from odoo import api, models
from odoo.exceptions import UserError


def _decode_qif_bytes(data_file):
    """Bancos suelen exportar QIF en Windows-1252/Latin-1, no en UTF-8."""
    raw = (data_file or b"").strip()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _qif_lines_from_text(file_data):
    """Normaliza CRLF/CR; evita partir solo por \\r y dejar \\n pegado a campos."""
    text = file_data.replace("\r\n", "\n").replace("\r", "\n")
    return text.split("\n")


def _qif_unique_import_id(vals_line, seq):
    """Identificador estable para deduplicar líneas (el QIF no trae ID de banco)."""
    base = "|".join(
        [
            str(vals_line.get("date") or ""),
            str(vals_line.get("amount") or ""),
            str(vals_line.get("ref") or ""),
            str(vals_line.get("payment_ref") or ""),
            str(seq),
        ]
    )
    return hashlib.sha256(base.encode("utf-8", "replace")).hexdigest()[:32]


class AccountStatementImport(models.TransientModel):
    _inherit = "account.statement.import"

    @api.model
    def _check_qif(self, data_file):
        return data_file.strip().startswith(b"!Type:")

    def _parse_file(self, data_file):
        if not self._check_qif(data_file):
            return super()._parse_file(data_file)
        try:
            file_data = _decode_qif_bytes(data_file)
            data_list = _qif_lines_from_text(file_data)
            header_line = next((ln.strip() for ln in data_list if ln.strip()), "")
            _atype, sep, header = header_line.partition(":")
            if not sep or not header.strip():
                raise ValueError("missing QIF type header")
            header = header.strip()
        except Exception as e:
            raise UserError(self.env._("Could not decipher the QIF file.")) from e

        journal = self.env["account.journal"].browse(
            self.env.context.get("journal_id")
            or (self.journal_id.id if self.journal_id else False)
        )
        dayfirst = True
        fmt = getattr(journal, "qif_date_format", None)
        if fmt == "month_first":
            dayfirst = False
        elif fmt == "day_first":
            dayfirst = True
        transactions = []
        vals_line = {}
        total = 0
        if header in ("Bank", "Cash", "CCard"):
            vals_bank_statement = {}
            for line in data_list:
                line = line.strip()
                if not line:
                    continue
                if line[0] == "D":  # date of transaction
                    vals_line["date"] = dateutil.parser.parse(
                        line[1:], fuzzy=True, dayfirst=dayfirst
                    ).date()
                elif line[0] == "T":  # Total amount
                    total += float(line[1:].replace(",", ""))
                    vals_line["amount"] = float(line[1:].replace(",", ""))
                elif line[0] == "N":  # Check number
                    vals_line["ref"] = line[1:]
                elif line[0] == "P":  # Payee
                    vals_line["payment_ref"] = (
                        "name" in vals_line
                        and line[1:] + ": " + vals_line["name"]
                        or line[1:]
                    )
                elif line[0] == "M":  # Memo
                    vals_line["payment_ref"] = (
                        "name" in vals_line
                        and vals_line["name"] + ": " + line[1:]
                        or line[1:]
                    )
                elif line[0] == "^" and vals_line:  # end of item
                    vals_line["unique_import_id"] = _qif_unique_import_id(
                        vals_line, len(transactions) + 1
                    )
                    transactions.append(vals_line)
                    vals_line = {}
                elif line[0] == "\n":
                    transactions = []
                else:
                    pass
        else:
            raise UserError(
                self.env._(
                    "This file is either not a bank statement or is "
                    "not correctly formed."
                )
            )
        vals_bank_statement.update(
            {"balance_end_real": total, "transactions": transactions}
        )
        if journal:
            currency = journal.currency_id or journal.company_id.currency_id
        else:
            currency = False
        if not currency:
            currency = self.env.company.currency_id
        currency_code = currency.name if currency else False
        # El QIF no incluye IBAN/cuenta: si ya hay diario, reutilizamos la cuenta del diario
        # para que `_match_journal` resuelva el diario como con OFI/CSV.
        account_number = None
        if journal and journal.bank_account_id:
            account_number = journal.bank_account_id.acc_number
        return currency_code, account_number, [vals_bank_statement]

    def _complete_stmts_vals(self, stmt_vals, journal_id, account_number):
        """Match partner_id if hasn't been deducted yet."""
        res = super()._complete_stmts_vals(stmt_vals, journal_id, account_number)
        # Since QIF doesn't provide account numbers (normal behaviour is to
        # provide 'account_number', which the generic module uses to find
        # the partner), we have to find res.partner through the name
        if not self.statement_file or not self._check_qif(
            base64.b64decode(self.statement_file)
        ):
            return res
        partner_obj = self.env["res.partner"]
        for statement in res:
            for line_vals in statement["transactions"]:
                if not line_vals.get("partner_id") and line_vals.get("payment_ref"):
                    partner = partner_obj.search(
                        [("name", "ilike", line_vals["payment_ref"])],
                        limit=1,
                    )
                    line_vals["partner_id"] = partner.id
        return res
