# -*- coding: utf-8 -*-
# Carga explícita de modelos; sin esto Python no ejecuta estos módulos y el
# registro de Odoo queda sin p. ej. debit.credit (RPC 404).

from . import manual_payment_mixin
from . import usd_rate_mixin
from . import gn_banks_document_journal_mixin
from . import account_journal
from . import ir_sequence
from . import res_company
from . import account_move
from . import account_payment
from . import check_format
from . import bank_templates
from . import debit_credit
from . import bank_provision
from . import bank_check
from . import bank_transfer
from . import documents
