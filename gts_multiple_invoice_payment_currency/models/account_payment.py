
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


def _gts_compute_sequence_code(partner_type, payment_type):
    mapping = {
        ("customer", "inbound"): "account.payment.customer.invoice",
        ("customer", "outbound"): "account.payment.customer.refund",
        ("supplier", "inbound"): "account.payment.supplier.refund",
        ("supplier", "outbound"): "account.payment.supplier.invoice",
    }
    return mapping.get((partner_type, payment_type))


def _gts_find_payment_sequence(env, company, journal, payment_type, sequence_code=None):
    """Locate the sequence record that should be used for a payment."""
    Sequence = env["ir.sequence"].with_company(company)

    # Buscar secuencias en diarios con múltiples secuencias habilitadas
    if (
        journal
        and journal.type in ("bank", "cash")
        and "bank_multi_sequence" in journal._fields
        and "sequence_ids" in journal._fields
        and journal.bank_multi_sequence
    ):
        # Mapeo de tipos de pago a tipos de secuencia
        payment_to_sequence_type = {
            "deposit": "deposit",
            "check": "check",
            "transference": "transference",
            "credit_card": "credit_card",
            "caja": "caja",
            "otro": "otro",
        }
        
        # Obtener el tipo de secuencia correspondiente al tipo de pago
        sequence_type = payment_to_sequence_type.get(payment_type)
        
        # Si el tipo de pago está en el mapeo, buscar la secuencia específica
        if sequence_type:
            # Buscar secuencias del tipo correspondiente
            sequences = journal.sequence_ids.filtered(lambda seq: seq.move_type == sequence_type)
            if company:
                sequences = sequences.filtered(
                    lambda seq: not seq.company_id or seq.company_id == company
                )
            if sequences:
                return sequences[0]
            # Si el diario tiene múltiples secuencias habilitadas pero no se encontró la secuencia específica,
            # NO usar la secuencia genérica, retornar vacío para mostrar "Sin secuencia configurada"
            return Sequence.browse()
        elif payment_type:
            # Si el tipo de pago existe pero no está en el mapeo (no es un tipo válido para múltiples secuencias),
            # retornar vacío para mostrar "Sin secuencia configurada"
            return Sequence.browse()
        # Si no hay tipo de pago, continuar con la búsqueda de secuencias genéricas

    codes = []
    if sequence_code:
        codes.append(sequence_code)
    if payment_type:
        if journal:
            codes.append(f"gts.payment.{payment_type}.{journal.id}")
            if journal.code:
                codes.append(f"gts.payment.{journal.code}.{payment_type}")
        codes.extend(
            [
                f"gts.payment.{payment_type}",
                f"account.payment.{payment_type}",
            ]
        )
    codes.append("account.payment")

    seen = set()
    unique_codes = [c for c in codes if c and (c not in seen and not seen.add(c))]
    if not unique_codes:
        return Sequence.browse()
    sequences = Sequence.search([("code", "in", unique_codes)])
    code_to_seq = {s.code: s for s in sequences}
    for code in unique_codes:
        if code in code_to_seq:
            return code_to_seq[code]
    return Sequence.browse()


class PaymentInvoiceLine(models.Model):
    _name = 'payment.invoice.line'
    _description = 'Payment Invoice Lines'

    @api.model
    def _get_invoice_domain(self):
        #if self.env.context.get('active_domain'):
        #    return self.env.context.get('active_domain')
        #elif self.env.context.get('inv_line_domain'):
        #    return self.env.context.get('inv_line_domain')
        #else:
        return []

    invoice_id = fields.Many2one('account.move', 'Invoice',domain=_get_invoice_domain)
    payment_id = fields.Many2one('account.payment', 'Related Payment')
    partner_id = fields.Many2one('res.partner', related='invoice_id.partner_id', string='Partner')
    amount_total = fields.Monetary('Amount Total')
    residual = fields.Monetary('Amount Due')
    amount = fields.Monetary('Amount To Pay',
        help="Enter amount to pay for this invoice, supports partial payment")
    actual_amount = fields.Float(compute='compute_actual_amount',
                                 string='Actual amount paid',
                                 help="Actual amount paid in journal currency")
    date_invoice = fields.Date(related='invoice_id.invoice_date', string='Invoice Date')
    currency_id = fields.Many2one(related='invoice_id.currency_id', string='Currency')
    company_id = fields.Many2one(related='payment_id.company_id', string='Company')
    supplier_invoice_number = fields.Char(string='Invoice Nº')
    payment_type = fields.Selection(related='payment_id.payment_type', store=True, readonly=True)

    @api.depends('amount', 'payment_id.date')
    def compute_actual_amount(self):
        for line in self:
            if line.amount > 0:
                line.actual_amount = line.currency_id._convert(
                    line.amount, line.payment_id.currency_id, self.env.user.company_id , line.payment_id.date,
                    round=False)
            else:
                line.actual_amount = 0.0


    def _get_max_amount_payable(self):
        """Residual de la factura. amount (neto banco) + retenciones debe ser <= residual."""
        self.ensure_one()
        if not self.invoice_id:
            return 0.0
        currency = self.currency_id or self.invoice_id.currency_id
        return currency.round(self.invoice_id.amount_residual) if currency else self.invoice_id.amount_residual

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if not line.invoice_id:
                continue
            if line.amount < 0:
                raise UserError(_('Amount to pay can not be less than 0! (Invoice code: %s)')
                    % line.invoice_id.name)
            total_retention = sum(
                getattr(line, f, 0.0) or 0.0
                for f in ('amount_retention_1', 'amount_retention_12_5', 'amount_retention_15')
            )
            total_covered = line.amount + total_retention
            max_residual = line._get_max_amount_payable()
            currency = line.currency_id or line.invoice_id.currency_id
            exceeds = (currency.compare_amounts(total_covered, max_residual) > 0
                       if currency
                       else total_covered > max_residual)
            if exceeds:
                raise UserError(_('"Amount to pay" can not be greater than "Amount '
                                  'Due" ! (Invoice code: %s)')
                                % line.invoice_id.name)

    @api.onchange('invoice_id')
    def onchange_invoice(self):
        if self.invoice_id:
            self.amount_total = self.invoice_id.amount_total
            self.residual = self.invoice_id.amount_residual
        else:
            self.amount_total = 0.0
            self.residual = 0.0


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    invoice_lines = fields.One2many('payment.invoice.line', 'payment_id', 'Invoice Lines',
        help='Please select invoices for this partner for the payment')
    selected_inv_total = fields.Float(compute='compute_selected_invoice_total',
        store=True, string='Assigned Amount')
    balance = fields.Float(compute='_compute_balance', string='Balance')

    payment_move_type = fields.Selection(
        selection='_get_payment_move_type_selection',
        string="Payment Transaction Type"
    )
    payment_move_type_dep = fields.Selection(
        [('deposit', 'Deposit')], string="Payment Transaction Type (Deposit)"
    )
    is_cancel = fields.Boolean(string="Cancelled", copy=False)
    old_number = fields.Char(string="Old Number", copy=False, help="hold value of number field")

    @api.model
    def _get_payment_move_type_selection(self):
        """Obtener las opciones de tipo de transacción basadas en las secuencias del diario.
        Para pagos outbound (proveedores), solo mostrar: cheques, transferencias, tarjeta de crédito, otro.
        """
        # Opciones base permitidas para proveedores
        return [
            ('check', 'Cheques'),
            ('cash', 'Efectivo'),
            ('transference', 'Transferencias'),
            ('credit_card', 'Tarjeta de Crédito'),
            ('caja', 'Caja'),
            ('otro', 'Otro'),
        ]

    def _get_available_payment_move_types(self):
        """Obtener los tipos de transacción disponibles basados en las secuencias del diario.
        Retorna una lista de códigos de tipos disponibles.
        """
        self.ensure_one()
        
        # Mapeo de tipos de secuencia a códigos de pago
        type_mapping = {
            'check': 'check',
            'cash': 'cash',
            'transference': 'transference',
            'credit_card': 'credit_card',
            'caja': 'caja',
            'otro': 'otro',
        }
        
        # Solo para pagos outbound (proveedores)
        if self.payment_type != 'outbound' or not self.journal_id:
            return list(type_mapping.values())
        
        # Verificar si el diario tiene múltiples secuencias habilitadas
        if (hasattr(self.journal_id, 'bank_multi_sequence') and 
            hasattr(self.journal_id, 'sequence_ids') and 
            self.journal_id.bank_multi_sequence):
            
            # Obtener los tipos de transacción configurados en las secuencias del diario
            sequences = self.journal_id.sequence_ids.filtered(
                lambda s: s.move_type in type_mapping.keys()
            )
            available_types = sequences.mapped('move_type')
            
            # Filtrar solo los tipos permitidos para proveedores
            allowed_types = ['check', 'cash', 'transference', 'credit_card', 'caja', 'otro']
            available_types = [t for t in available_types if t in allowed_types]
            
            # Retornar los códigos disponibles
            if available_types:
                return [type_mapping[t] for t in available_types if t in type_mapping]
        
        # Por defecto, retornar todas las opciones permitidas
        return list(type_mapping.values())

    def unlink(self):
        for payment in self:
            if payment.move_id.posted_before and not self._context.get('force_delete'):
                raise UserError(_("You cannot delete an payment which has been posted once."))
        return super(AccountPayment, self).unlink()

    def button_open_move_lines(self):
        action = self.env.ref('account.action_account_moves_all').read()[0]
        action.update({'domain': [('id', 'in', self.move_id.line_ids.ids)]})
        return action

    def action_cancel(self):
        for payment in self:
            if payment.move_id and payment.move_id.state == 'posted':
                payment.move_id.line_ids.remove_move_reconcile()
        self.is_cancel = True
        self.old_number = self.name
        return super(AccountPayment, self.with_context(force_delete=True)).action_cancel()

    def action_draft(self):
        res = super(AccountPayment, self).action_draft()
        self.is_cancel = True

    def _gts_get_transaction_move_type(self):
        payment_type = self.payment_move_type_dep or self.payment_move_type
        if not payment_type and self.payment_type == 'inbound':
            payment_type = 'deposit'
        return payment_type

    def _gts_is_placeholder_payment_name(self, name):
        if not name:
            return True
        placeholders = {'/', 'Borrador', 'Draft', _('Sin secuencia configurada')}
        return name in placeholders

    def _gts_is_posted_name_taken(self, name, journal, exclude_move=None, exclude_payment=None):
        """True si un asiento publicado o un pago confirmado ya usa ese nombre en el diario."""
        if not name or not journal or self._gts_is_placeholder_payment_name(name):
            return False
        move_domain = [
            ('name', '=', name),
            ('journal_id', '=', journal.id),
            ('state', '=', 'posted'),
        ]
        exclude_move_id = exclude_move.id if exclude_move and isinstance(exclude_move.id, int) else None
        if exclude_move_id:
            move_domain.append(('id', '!=', exclude_move_id))
        if self.env['account.move'].sudo().search(move_domain, limit=1):
            return True
        payment_domain = [
            ('name', '=', name),
            ('journal_id', '=', journal.id),
            ('state', 'in', ('in_process', 'paid')),
        ]
        exclude_payment_id = (
            exclude_payment.id if exclude_payment and isinstance(exclude_payment.id, int) else None
        )
        if exclude_payment_id:
            payment_domain.append(('id', '!=', exclude_payment_id))
        return bool(self.sudo().search(payment_domain, limit=1))

    def _gts_next_free_payment_name(self, sequence):
        """Consume la secuencia hasta un nombre no usado por asiento/pago publicado."""
        self.ensure_one()
        if not sequence:
            return False
        seq = sequence.with_context(ir_sequence_date=self.date)
        max_attempts = 50
        for _attempt in range(max_attempts):
            new_name = seq.next_by_id()
            if not new_name:
                return False
            if not self._gts_is_posted_name_taken(
                new_name,
                self.journal_id,
                exclude_move=self.move_id,
                exclude_payment=self,
            ):
                return new_name
            _logger.info(
                "gts payment sequence: skipped occupied name %s on journal %s",
                new_name,
                self.journal_id.id,
            )
        raise UserError(_(
            "No se encontró un número de secuencia libre tras %(attempts)s intentos "
            "en el diario %(journal)s. Resincronice la secuencia."
        ) % {'attempts': max_attempts, 'journal': self.journal_id.display_name})

    def _gts_clear_colliding_draft_name(self):
        """Evita publicar un asiento con un nombre ya usado (el constraint salta al post)."""
        for rec in self:
            if rec.is_cancel or not rec.journal_id:
                continue
            if rec._gts_is_posted_name_taken(
                rec.name, rec.journal_id, exclude_move=rec.move_id, exclude_payment=rec
            ):
                rec.with_context(skip_payment_write_lock=True).name = '/'
                if rec.move_id and rec.move_id.state != 'posted':
                    rec.move_id.name = '/'

    @api.onchange('journal_id', 'payment_type')
    def _onchange_journal_payment_type(self):
        """Actualizar payment_move_type cuando cambia el diario o tipo de pago."""
        if self.payment_type == 'outbound' and self.journal_id:
            # Obtener los tipos disponibles en el diario
            available_types = self._get_available_payment_move_types()
            
            # Si el tipo actual no está disponible, limpiarlo
            if self.payment_move_type and self.payment_move_type not in available_types:
                self.payment_move_type = False
        
        # Llamar a get_msg_number para actualizar la secuencia
        self.get_msg_number()

    @api.onchange('journal_id', 'payment_move_type', 'payment_move_type_dep', 'payment_type')
    def get_msg_number(self):
        if not self.journal_id:
            # Si no hay diario, limpiar el nombre
            if self.state in (False, 'draft'):
                self.name = _("Sin secuencia configurada")
            return
            
        if self.state not in (False, 'draft'):
            return

        # Asegurar que payment_move_type_dep esté establecido para pagos inbound
        if self.payment_type == 'inbound' and not self.payment_move_type_dep:
            self.payment_move_type_dep = 'deposit'

        sequence_code = _gts_compute_sequence_code(self.partner_type, self.payment_type)
        payment_type = self._gts_get_transaction_move_type()

        if self.payment_move_type_dep and self.journal_id.type == 'general':
            # keep legacy behaviour for general journals
            self.name = ''
            return

        # Para pagos outbound, si no hay tipo de transacción, mostrar mensaje
        if self.payment_type == 'outbound' and not payment_type:
            self.name = _("Sin secuencia configurada")
            return

        if not payment_type and not sequence_code:
            self.name = _("Sin secuencia configurada")
            return

        sequence = _gts_find_payment_sequence(
            self.env,
            self.company_id,
            self.journal_id,
            payment_type,
            sequence_code,
        )

        if sequence:
            preview = sequence.with_context(ir_sequence_date=self.date).get_next_char(sequence.number_next_actual)
            if preview:
                self.name = preview
            else:
                self.name = _("Sin secuencia configurada")
        else:
            self.name = _("Sin secuencia configurada")

    def update_seq(self, sequence=None, payment_type=None, sequence_code=None):
        self.ensure_one()
        payment_type = payment_type or self._gts_get_transaction_move_type()
        sequence_code = sequence_code or _gts_compute_sequence_code(self.partner_type, self.payment_type)

        if self.payment_move_type_dep and self.journal_id.type == 'general':
            sequence = sequence or _gts_find_payment_sequence(
                self.env,
                self.company_id,
                self.journal_id,
                payment_type,
                sequence_code,
            )
            if sequence:
                self.name = sequence.with_context(ir_sequence_date=self.date).get_next_char(
                    sequence.number_next_actual
                )
            return

        sequence = sequence or _gts_find_payment_sequence(
            self.env,
            self.company_id,
            self.journal_id,
            payment_type,
            sequence_code,
        )
        if not sequence or sequence.code == 'account.payment':
            return

        preview = sequence.with_context(ir_sequence_date=self.date).get_next_char(sequence.number_next_actual + 1)
        other_payments = self.env["account.payment"].search(
            [
                ("state", "=", "draft"),
                ("payment_move_type", "=", payment_type),
                ("journal_id", "=", self.journal_id.id),
                ("is_cancel", "=", False),
            ]
        )
        if preview and other_payments:
            other_payments.write({"name": preview})

    def get_sequence(self):
        payment_type = self._gts_get_transaction_move_type()
        sequence_code = _gts_compute_sequence_code(self.partner_type, self.payment_type)
        sequence = _gts_find_payment_sequence(
            self.env,
            self.company_id,
            self.journal_id,
            payment_type,
            sequence_code,
        )
        if not sequence:
            sequence = self.env['ir.sequence'].with_company(self.company_id).search(
                [('code', '=', 'account.payment')], limit=1
            )
        if sequence:
            return sequence.id
        raise ValidationError(_("Sin secuencia configurada"))

    @api.depends('invoice_lines', 'invoice_lines.amount', 'amount')
    def _compute_balance(self):
        for payment in self:
            total = 0.0
            for line in payment.invoice_lines:
                total += line.actual_amount
            balance = payment.amount - total
            if payment.company_id and payment.currency_id:
                payment.balance = payment.currency_id._convert(
                    balance, payment.currency_id, payment.company_id, payment.date,
                    round=False)
            else:
                payment.balance = balance

    @api.depends('invoice_lines', 'invoice_lines.amount', 'invoice_lines.actual_amount')
    def compute_selected_invoice_total(self):
        for payment in self:
            total = 0.0
            for line in payment.invoice_lines:
                total += line.actual_amount
            payment.selected_inv_total = total

    @api.constrains('amount', 'selected_inv_total', 'invoice_lines')
    def _check_invoice_amount(self):
        ''' Function to validate if user has selected more amount invoices than payment '''
        for payment in self:
            if payment.invoice_lines:
                diff = payment.selected_inv_total - payment.amount
                tolerance = 0.05
                if diff <= tolerance:
                    continue
                retention_total = 0.0
                for line in payment.invoice_lines:
                    retention_total += sum(filter(None, [
                        getattr(line, 'amount_retention_1', 0.0) or getattr(getattr(line, 'invoice_id', False), 'ret_amount_1', 0.0),
                        getattr(line, 'amount_retention_12_5', 0.0) or getattr(getattr(line, 'invoice_id', False), 'ret_amount_12_5', 0.0),
                        getattr(line, 'amount_retention_15', 0.0) or getattr(getattr(line, 'invoice_id', False), 'ret_amount_15', 0.0),
                    ]))

                if diff - retention_total > tolerance:
                    raise UserError(_('No puede seleccionar facturas por un monto mayor al pago.'))

    @api.onchange('partner_id', 'payment_type')
    def onchange_partner_id(self):
        if self.payment_type == 'inbound':
            self.payment_move_type_dep = 'deposit'
            
        else:
            self.payment_move_type_dep = False
        Invoice = self.env['account.move']
        PaymentLine = self.env['payment.invoice.line']
        context = self.env.context
        if context.get('active_model', '') == 'account.move':
            self.invoice_lines = []
            return
        if self.partner_id and not self.reconciled_invoice_ids:
            partners_list = self.partner_id.child_ids.ids
            partners_list.append(self.partner_id.id)
            line_ids = []
            type = ''
            if self.payment_type == 'outbound':
                type = 'in_invoice'
            elif self.payment_type == 'inbound':
                type = 'out_invoice'
            invoices = Invoice.search([('partner_id', 'in', partners_list),
                                       ('state', 'in', ('posted',)), ('move_type', '=', type),
                                       ('amount_residual', '>', 0.0)], order="invoice_date")
            supplier_number = ''
            for invoice in invoices:
                if self.payment_type == 'outbound':
                    supplier_number = invoice.supplier_invoice_number
                data = {
                    'invoice_id': invoice.id,
                    'amount_total': invoice.amount_total,
                    'residual': invoice.amount_residual,
                    'amount': 0.0,
                    'date_invoice': invoice.invoice_date,
                    'supplier_invoice_number': supplier_number
                }
                # line = PaymentLine.create(data)
                line_ids.append((0, 0, data))
            self.invoice_lines = [(5, 0, 0)] + line_ids
        else:
            if self.invoice_lines:
                for line in self.invoice_lines:
                    line.unlink()
            self.invoice_lines = []

    @api.onchange('amount')
    def onchange_amount(self):
        ''' Function to reset/select invoices on the basis of invoice date '''
        if self.amount > 0 and self.invoice_lines:
            total_amount = self.amount
            for line in self.invoice_lines:
                if total_amount > 0:
                    conv_amount = self.currency_id._convert(
                        total_amount, line.currency_id, self.env.user.company_id, self.date, round=False)
                    if line.residual < conv_amount:
                        line.amount = line.residual
                        if line.currency_id.id == self.currency_id.id:
                            total_amount -= line.residual
                        else:
                            spend_amount = line.currency_id._convert(
                                line.residual, self.currency_id, self.company_id, self.date, round=False)
                            total_amount -= spend_amount
                    else:
                        line.amount = self.currency_id._convert(
                            total_amount, line.currency_id, self.env.user.company_id, self.date, round=False)
                        total_amount = 0
                else:
                    line.amount = 0.0
        if (self.amount <= 0):
            for line in self.invoice_lines:
                line.amount = 0.0

    def action_post(self):
        """ Function reconcile selected invoices """
        reconcile_obj = self.env['account.partial.reconcile']
        move_line_obj = self.env['account.move.line']
        # Remove invoice lines with zero assigned amounts before posting
        zero_amount_lines = self.invoice_lines.filtered(lambda line: line.amount <= 0.0)
        if zero_amount_lines:
            zero_amount_lines.unlink()
        self._gts_clear_colliding_draft_name()
        res = super(AccountPayment, self).action_post()
        # Tras publicar, asignar secuencia/nombre es parte del alta del pago (no edición manual).
        for rec in self.with_context(skip_payment_write_lock=True):
            # create sequence number before post
            if rec.name:
                if len(rec.name) > 50:
                        raise ValidationError(self.name)
            
            # Asegurar que payment_move_type_dep esté establecido para pagos inbound
            if rec.payment_type == 'inbound' and not rec.payment_move_type_dep:
                rec.payment_move_type_dep = 'deposit'
            
            # Si el nombre es "Borrador" o está vacío, establecer la secuencia
            needs_sequence = rec._gts_is_placeholder_payment_name(rec.name)
            
            if not rec.is_cancel:
                payment_type = rec._gts_get_transaction_move_type()
                sequence_code = _gts_compute_sequence_code(rec.partner_type, rec.payment_type)
                sequence = _gts_find_payment_sequence(
                    self.env,
                    rec.company_id,
                    rec.journal_id,
                    payment_type,
                    sequence_code,
                )
                # Establecer la secuencia si existe y no es la secuencia genérica, o si el nombre es inválido
                if sequence and (sequence.code != 'account.payment' or needs_sequence):
                    new_name = rec._gts_next_free_payment_name(sequence)
                    if new_name:
                        rec.move_id.name = new_name
                        rec.name = new_name
                        rec.update_seq(sequence=sequence, payment_type=payment_type, sequence_code=sequence_code)

            # remove invoice which dont have amount allocation
            invoice_lines = rec.invoice_lines.filtered(lambda line: line.amount <= 0.0)
            invoice_lines.unlink()

            invoice_lines = rec.invoice_lines.filtered(lambda line: line.amount > 0.0)
            if not invoice_lines:
                return res
            company_currency = rec.company_id.currency_id
            move_lines = move_line_obj.search([('payment_id', '=', rec.id)])
            for line in invoice_lines:
                total_retention = sum(
                    getattr(line, f, 0.0) or 0.0
                    for f in ('amount_retention_1', 'amount_retention_12_5', 'amount_retention_15')
                )
                total_to_reconcile = line.amount + total_retention
                if rec.currency_id == company_currency:
                    amount = total_to_reconcile
                    amount_currency = total_to_reconcile
                    currency_id = rec.currency_id.id
                else:
                    amount_currency = total_to_reconcile
                    currency_id = line.currency_id.id
                    amount = line.currency_id._convert(
                        total_to_reconcile, company_currency, rec.company_id,
                        rec.date, round=False)
                if rec.payment_type == 'outbound':
                    credit_lines = move_lines.filtered(lambda l: l.debit > 0.0)
                    if not credit_lines:
                        continue
                    for credit_line in credit_lines:
                        invoice_debit_line = line.invoice_id.line_ids.filtered(
                            lambda l: l.account_id.id == credit_line.account_id.id)
                        if not invoice_debit_line:
                            continue
                        for debit_line in invoice_debit_line:
                            data = {
                                'debit_move_id': debit_line.id,
                                'credit_move_id': credit_line.id,
                                'amount': -amount,
                                'credit_amount_currency': -amount_currency,
                                'debit_amount_currency': -amount_currency,
                                'credit_currency_id': currency_id or False,
                            }
                            reconcile_obj.create(data)
                            invoice_debit_line.filtered(lambda l: not l.reconciled).reconcile()
                if rec.payment_type == 'inbound':
                    credit_lines = move_lines.filtered(lambda l: l.credit > 0.0)
                    if not credit_lines:
                        continue
                    for credit_line in credit_lines:
                        invoice_debit_line = line.invoice_id.line_ids.filtered(
                            lambda l: l.account_id.id == credit_line.account_id.id)
                        if not invoice_debit_line:
                            continue
                        for debit_line in invoice_debit_line:
                            reconcile_obj.create({
                                'debit_move_id': debit_line.id,
                                'credit_move_id': credit_line.id,
                                'amount': amount,
                                'credit_amount_currency': amount_currency,
                                'debit_amount_currency': amount_currency,
                                'credit_currency_id': currency_id or False,
                            })
                            invoice_debit_line.filtered(lambda l: not l.reconciled).reconcile()
        return res

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update(invoice_lines=[])
        return super(AccountPayment, self).copy(default)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.depends('line_ids')
    def _compute_from_lines(self):
        super()._compute_from_lines()
        for wizard in self:
            # Pagos a proveedor: siempre mostrar/editar payment_date (no ocultar tras reconcile_with_invoice_date).
            if wizard.partner_type == 'supplier':
                wizard.reconcile_with_invoice_date = False

    name = fields.Char(string="Name")
    payment_move_type = fields.Selection([('check', 'Cheques'),
                                          ('cash', 'Efectivo'),
                                          ('transference', 'Transfer'),
                                          ('credit_card', 'Tarjeta de Crédito'),
                                          ('caja', 'Caja'),
                                          ('otro', 'Otro')], string="Payment Transaction Type")
    payment_move_type_dep = fields.Selection(
        [('deposit', 'Deposit')], string="Payment Transaction Type (Deposit)"
    )

    reconcile_with_invoice_date = fields.Boolean(
        string="Reconciliar con fecha de factura",
        help="Si está activo, el pago se generará y conciliará con la(s) fecha(s) de factura "
             "para evitar diferencias de cambio y luego se restaurará la fecha real del pago."
    )
    
    real_payment_date = fields.Date(
        string="Fecha de pago",
        help="Fecha operativa real; el asiento se creará/conciliará con fecha de factura "
             "y luego se restaurará a esta fecha.",
        default=date.today()
    )
    
    @api.onchange('reconcile_with_invoice_date')
    def _onchange_reconcile_with_invoice_date(self):
        if self.reconcile_with_invoice_date:
            self.payment_date = self.line_ids[0].move_id.invoice_date if self.line_ids else False
            
    def _create_payments(self):
        payments = super()._create_payments()
        if self.reconcile_with_invoice_date and self.real_payment_date:
            payments.with_context(skip_payment_write_lock=True).write({
                'date': self.real_payment_date,
            })
            moves = self.env['account.move'].search([('payment_id', 'in', payments.ids)])
            moves.write({'date': self.real_payment_date})
        return payments

    def _hn_get_invoice_fx_date_from_batch(self, batch_result):
        """Return a single date to use for FX conversion when the original method
        would have used self.payment_date. We pick the earliest invoice date among
        the lines in the batch (fallback to move.date, then payment_date)."""
        self.ensure_one()
        dates = []
        for aml in batch_result.get("lines", []):
            move = aml.move_id
            fx_date = move.invoice_date or move.date or self.payment_date
            if fx_date:
                dates.append(fx_date)
        return min(dates) if dates else self.payment_date

    def _hn_get_invoice_fx_date_per_line(self, aml):
        """Line-level FX date (invoice_date > move.date > payment_date)."""
        move = aml.move_id
        return move.invoice_date or move.date or self.payment_date
    
    ## Se cambio para que se pueda usar la fecha de la factura en lugar de la fecha de pago
    def _get_total_amount_in_wizard_currency_to_full_reconcile(self, batch_result, early_payment_discount=True):
        """ Compute the total amount needed in the currency of the wizard to fully reconcile the batch of journal
        items passed as parameter.

        :param batch_result:    A batch returned by '_get_batches'.
        :return:                An amount in the currency of the wizard.
        """
        self.ensure_one()

        comp_curr = self.company_id.currency_id
        if self.source_currency_id == self.currency_id:
            self.reconcile_with_invoice_date = False
            # Same currency (manage the early payment discount).
            return self._get_total_amount_using_same_currency(batch_result, early_payment_discount=early_payment_discount)
        elif self.source_currency_id != comp_curr and self.currency_id == comp_curr:
            # Foreign currency on source line but the company currency one on the opposite line.
            fx_date = self._hn_get_invoice_fx_date_from_batch(batch_result)

            # Conversión sin redondeo
            amount_converted = self.source_currency_id._convert(
                self.source_amount_currency,
                comp_curr,
                self.company_id,
                fx_date,
                round=False
            )

            # Obtenemos la factura (todas las líneas deberían pertenecer a la misma factura en este caso)
            invoice = batch_result['lines'][0].move_id if batch_result.get('lines') else None
            if invoice:
                diff = invoice.amount_total_signed - amount_converted
                tolerance = 0.02  # margen para absorber diferencias pequeñas

                # Si la diferencia está dentro del margen, se ajusta
                if abs(diff) <= tolerance:
                    amount_converted += diff

            # Redondeo final usando la moneda de la compañía
            amount_converted = comp_curr.round(amount_converted)
            self.reconcile_with_invoice_date = True
            self.payment_date = fx_date
            return amount_converted, False
            
        elif self.source_currency_id == comp_curr and self.currency_id != comp_curr:
            # Company currency on source line but a foreign currency one on the opposite line.
            residual_amount = 0.0
            for aml in batch_result['lines']:
                if not aml.move_id.payment_id and not aml.move_id.statement_line_id:
                    conversion_date = self._hn_get_invoice_fx_date_per_line(aml)
                else:
                    conversion_date = self._hn_get_invoice_fx_date_per_line(aml)
                residual_amount += comp_curr._convert(
                    aml.amount_residual,
                    self.currency_id,
                    self.company_id,
                    conversion_date,
                )
            self.reconcile_with_invoice_date = True
            self.payment_date = self._hn_get_invoice_fx_date_from_batch(batch_result)
            return abs(residual_amount), False
        else:
            # Foreign currency on payment different than the one set on the journal entries.
            fx_date = self._hn_get_invoice_fx_date_from_batch(batch_result)
            self.reconcile_with_invoice_date = True
            self.payment_date = fx_date
            return comp_curr._convert(
                self.source_amount,
                self.currency_id,
                self.company_id,
                fx_date,
            ), False
        
    @api.onchange('payment_type')
    def _onchange_payment_type_seq(self):
        if self.payment_type == 'inbound':
            self.payment_move_type_dep = 'deposit'
        else:
            self.payment_move_type_dep = False

    def _gts_get_transaction_move_type(self):
        payment_type = self.payment_move_type_dep or self.payment_move_type
        if not payment_type and self.payment_type == 'inbound':
            payment_type = 'deposit'
        return payment_type

    @api.onchange('journal_id', 'payment_move_type', 'payment_move_type_dep', 'payment_type')
    def get_msg_number(self):
        if not self.journal_id:
            return

        payment_type = self._gts_get_transaction_move_type()
        sequence_code = _gts_compute_sequence_code(self.partner_type, self.payment_type)

        if self.payment_move_type_dep and self.journal_id.type == 'general':
            sequence = _gts_find_payment_sequence(
                self.env,
                self.company_id,
                self.journal_id,
                payment_type,
                sequence_code,
            )
            if sequence:
                self.name = sequence.with_context(ir_sequence_date=self.payment_date).get_next_char(
                    sequence.number_next_actual
                )
            return

        if not payment_type and not sequence_code:
            return

        sequence = _gts_find_payment_sequence(
            self.env,
            self.company_id,
            self.journal_id,
            payment_type,
            sequence_code,
        )
        if sequence:
            self.name = sequence.with_context(ir_sequence_date=self.payment_date).get_next_char(
                sequence.number_next_actual
            )
        else:
            self.name = _("Sin secuencia configurada")

    def update_seq(self, sequence=None, payment_type=None, sequence_code=None):
        payment_type = payment_type or self._gts_get_transaction_move_type()
        sequence_code = sequence_code or _gts_compute_sequence_code(self.partner_type, self.payment_type)

        sequence = sequence or _gts_find_payment_sequence(
            self.env,
            self.company_id,
            self.journal_id,
            payment_type,
            sequence_code,
        )
        if not sequence or sequence.code == 'account.payment':
            return

        preview = sequence.with_context(ir_sequence_date=self.payment_date).get_next_char(
            sequence.number_next_actual + 1
        )
        if not preview:
            return
        draft_payments = self.env["account.payment"].search(
            [
                ("state", "=", "draft"),
                ("payment_move_type", "=", payment_type),
                ("journal_id", "=", self.journal_id.id),
                ("is_cancel", "=", False),
            ]
        )
        if draft_payments:
            draft_payments.write({"name": preview})

    def get_sequence(self):
        payment_type = self._gts_get_transaction_move_type()
        sequence_code = _gts_compute_sequence_code(self.partner_type, self.payment_type)
        sequence = _gts_find_payment_sequence(
            self.env,
            self.company_id,
            self.journal_id,
            payment_type,
            sequence_code,
        )
        if not sequence:
            sequence = self.env['ir.sequence'].with_company(self.company_id).search(
                [('code', '=', 'account.payment')], limit=1
            )
        if sequence:
            return sequence.id
