import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Formato SAR Honduras: 000-002-01-00022827 (19 caracteres)
CUSTOMER_REF_INVOICE_RE = re.compile(r'^\d{3}-\d{3}-\d{2}-\d{8}$')
CUSTOMER_REF_INVOICE_LEN = 19


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_hn_customer_ref_ready = fields.Boolean(
        string='Lista para validar por referencia SAR',
        compute='_compute_l10n_hn_customer_ref_ready',
        help='Indica si la referencia del cliente cumple el formato SAR de 19 caracteres.',
    )

    @api.depends('ref', 'move_type', 'state')
    def _compute_l10n_hn_customer_ref_ready(self):
        for move in self:
            move.l10n_hn_customer_ref_ready = move._l10n_hn_customer_ref_is_valid_format(
                move.ref,
            )

    @api.model
    def _l10n_hn_customer_ref_is_valid_format(self, ref_value):
        ref_value = (ref_value or '').strip()
        return (
            len(ref_value) == CUSTOMER_REF_INVOICE_LEN
            and bool(CUSTOMER_REF_INVOICE_RE.match(ref_value))
        )

    def _l10n_hn_customer_ref_parse(self, ref_value):
        """Devuelve (prefijo, correlativo) a partir de la referencia SAR."""
        ref_value = (ref_value or '').strip()
        parts = ref_value.split('-')
        if len(parts) != 4:
            raise UserError(_(
                'La referencia del cliente debe tener el formato 000-002-01-00022827.'
            ))
        prefix = '-'.join(parts[:3])
        try:
            correlative = int(parts[3])
        except ValueError as exc:
            raise UserError(_(
                'El correlativo de la referencia del cliente debe ser numérico.'
            )) from exc
        return prefix, correlative

    def _l10n_hn_customer_ref_validate_for_post(self):
        """Comprueba formato SAR (19 caracteres) y que el número no esté duplicado."""
        self.ensure_one()
        if self.move_type != 'out_invoice':
            raise UserError(_(
                'Solo se puede validar por referencia del cliente en facturas de cliente.'
            ))
        if self.state != 'draft':
            raise UserError(_(
                'La factura %(name)s no está en borrador.',
                name=self.display_name,
            ))

        ref_value = (self.ref or '').strip()
        if not self._l10n_hn_customer_ref_is_valid_format(ref_value):
            raise UserError(_(
                'La referencia del cliente en la factura %(invoice)s debe tener '
                'exactamente 19 caracteres con el formato 000-002-01-00022827.',
                invoice=self.display_name,
            ))

        duplicate = self.search([
            ('id', '!=', self.id),
            ('name', '=', ref_value),
            ('company_id', '=', self.company_id.id),
            ('state', '!=', 'cancel'),
        ], limit=1)
        if duplicate:
            raise UserError(_(
                'El número %(number)s ya está asignado a la factura %(invoice)s.',
                number=ref_value,
                invoice=duplicate.display_name,
            ))

        return ref_value

    def _l10n_hn_customer_ref_assign_name(self, ref_value):
        """Asigna el número fiscal sin consumir la secuencia automática."""
        self.ensure_one()
        self.with_context(
            skip_compute_name=True,
            check_move_validity=False,
        ).write({
            'name': ref_value,
            'sequence_generated': True,
        })

    def _l10n_hn_customer_ref_sync_journal_sequence(self):
        """Avanza el contador del diario si la referencia supera el siguiente número."""
        for move in self.filtered(lambda m: m.move_type == 'out_invoice' and m.state == 'posted'):
            ref_value = (move.name or '').strip()
            if not move._l10n_hn_customer_ref_is_valid_format(ref_value):
                continue
            _prefix, correlative = move._l10n_hn_customer_ref_parse(ref_value)
            sequence = (
                move._get_sequence()
                if hasattr(move, '_get_sequence')
                else move.journal_id.sequence_id
            )
            if not sequence:
                continue
            next_actual = sequence.number_next_actual or 1
            if correlative >= next_actual:
                sequence.sudo().write({'number_next_actual': correlative + 1})

    def action_post_with_customer_ref(self):
        """Valida facturas de cliente usando ref como número fiscal (acción dedicada)."""
        if not self.env.user.has_group(
            'l10n_hn_customer_ref_invoice.group_customer_ref_invoice_post',
        ):
            raise AccessError(_(
                'No tiene permiso para validar facturas con referencia SAR. '
                'Solicite el grupo «Validar facturas con referencia SAR».'
            ))
        moves = self.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'draft',
        )
        if not moves:
            raise UserError(_(
                'Seleccione facturas de cliente en borrador para validar con referencia SAR.'
            ))

        skipped = self - moves
        if skipped:
            skipped_types = ', '.join(sorted(set(skipped.mapped('move_type'))))
            raise UserError(_(
                'Algunos documentos no son facturas de cliente en borrador '
                '(tipos: %(types)s). Solo se procesan facturas de cliente en borrador.',
                types=skipped_types,
            ))

        ref_by_move = {}
        for move in moves:
            ref_by_move[move.id] = move._l10n_hn_customer_ref_validate_for_post()

        for move in moves:
            move._l10n_hn_customer_ref_assign_name(ref_by_move[move.id])

        moves.with_context(
            l10n_hn_customer_ref_post=True,
            gn_labhospy_skip_sc_invoice_validation=True,
        ).action_post()
        moves._l10n_hn_customer_ref_sync_journal_sequence()
        return True

    @api.depends('posted_before', 'state', 'journal_id', 'date')
    def _compute_name(self):
        if self.env.context.get('skip_compute_name'):
            return
        if any(not isinstance(move.id, int) for move in self):
            draft_states = (False, 'draft')
            for move in self.filtered(lambda m: not isinstance(m.id, int)):
                if move.journal_id.sequence_id and move.state in draft_states:
                    move.name = '/'
            saved_moves = self.filtered(lambda m: isinstance(m.id, int))
            if not saved_moves:
                return
            return super(AccountMove, saved_moves)._compute_name()
        return super()._compute_name()
