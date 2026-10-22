# l10n_hn_base

Honduras localization **base accountant UI** for Odoo 19 Community.

## Implementation constraints (legal / architecture)

- **No Odoo Enterprise (OEEL) code** is copied or translated from `account_accountant` or other enterprise modules. Behavior is implemented as an independent LGPL-3 module using public Odoo CE APIs.
- **No OCA or third-party addon dependencies**; only `account` and `l10n_hn_account` are required.
- Critical business rules (reconciliation, posting, access) are enforced in **Python**, not only in the browser.

## Features

- Dedicated **bank statement line** list / form / search / kanban actions (“bank matching” style entry points).
- **Accounting dashboard** (bank/cash journals): shortcuts to reconcile, to review, all transactions, last statement.
- **Statement** form smart button to open the reconciliation view.
- **Accountant hub** client action (OWL) with quick links to bank operations and audit tools.
- **Audit helpers**: filters on journal entries and audit trail messages; optional stored **poster** metadata on `account.move`.

## Technical notes

OWL uses standard Odoo 19 web client services (`action`, `notification`, `orm`, `dialog` where used).
