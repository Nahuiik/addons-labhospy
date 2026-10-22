from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Estados en los que el pago ya fue confirmado/registrado (Odoo 19).
_PAYMENT_LOCKED_STATES = ('in_process', 'paid')

# Solo estos campos contables no pueden editarse en pagos registrados/pagados.
# El resto (style, comisiones calculadas, flags de UI, etc.) puede actualizarse
# durante el flujo de registro o por campos computados al confirmar.
_PAYMENT_WRITE_PROTECTED = frozenset({
    'partner_id',
    'amount',
    'currency_id',
    'journal_id',
    'date',
    'payment_type',
    'partner_type',
    'branch_id',
    'destination_account_id',
    'payment_method_line_id',
})


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    gts_no_exigir_sucursal = fields.Boolean(
        string='Sucursal Opcional',
        default=False,
        help='Si está activo, el campo Sucursal deja de ser obligatorio en este pago.',
    )

    @api.model
    def default_get(self, fields):
        rec = super().default_get(fields)
        rec.setdefault('branch_id', self.env.user.branch_id.id)
        context = dict(self.env.context)
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        if active_model and active_ids:
            invoices = self.env[active_model].browse(active_ids)
            if invoices:
                rec['branch_id'] = invoices[0].branch_id.id
        return rec

    branch_id = fields.Many2one('res.branch', string='Branch', default=lambda self: self.env.user.branch_id)

    payment_is_editable = fields.Boolean(
        compute='_compute_payment_is_editable',
        string='Pago editable',
    )

    @api.depends('state')
    def _compute_payment_is_editable(self):
        for payment in self:
            payment.payment_is_editable = payment.state in (False, 'draft')

    def _raise_if_locked_write(self, vals):
        """Impide modificar campos contables clave en pagos confirmados (in_process/paid)."""
        if self.env.context.get('skip_payment_write_lock'):
            return
        locked = self.filtered(lambda p: p.state in _PAYMENT_LOCKED_STATES)
        if not locked:
            return
        forbidden = set(vals.keys()) & _PAYMENT_WRITE_PROTECTED
        if forbidden:
            raise UserError(_(
                'No puede modificar un pago que ya está registrado o pagado. '
                'Campos bloqueados: %s. Use «Volver a borrador» si necesita corregirlo.'
            ) % ', '.join(sorted(forbidden)))

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        line_vals_list = super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
        )
        branch_id = self.branch_id.id
        if branch_id:
            for vals in line_vals_list:
                vals.setdefault('branch_id', branch_id)
        return line_vals_list

    def _generate_move_vals(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        move_vals = super()._generate_move_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
            line_ids=line_ids,
        )
        if self.branch_id:
            move_vals['branch_id'] = self.branch_id.id
        return move_vals

    def write(self, vals):
        self._raise_if_locked_write(vals)
        res = super().write(vals)
        if 'branch_id' in vals:
            for payment in self.filtered('move_id'):
                branch_id = payment.branch_id.id
                if not branch_id:
                    continue
                payment.move_id.with_context(
                    skip_invoice_sync=True,
                    skip_account_move_synchronization=True,
                    skip_readonly_check=True,
                ).write({'branch_id': branch_id})
                payment.move_id.line_ids.with_context(check_move_validity=False).write({'branch_id': branch_id})
        return res

    def action_draft(self):
        return super(
            AccountPayment,
            self.with_context(skip_payment_write_lock=True),
        ).action_draft()

    def action_cancel(self):
        return super(
            AccountPayment,
            self.with_context(skip_payment_write_lock=True),
        ).action_cancel()

    def action_post(self):
        return super(
            AccountPayment,
            self.with_context(skip_payment_write_lock=True),
        ).action_post()
