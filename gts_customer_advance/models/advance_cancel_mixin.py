# -*- coding: utf-8 -*-
"""Mixin: permiso de cancelación tardía en documentos de anticipos."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

ADVANCE_CANCEL_AFTER_DAY_GROUP = (
    'gts_customer_advance.group_advance_cancel_after_day'
)


class AdvanceCancelMixin(models.AbstractModel):
    _name = 'advance.cancel.mixin'
    _description = 'Control de cancelación tardía en anticipos'

    @api.model
    def _advance_user_can_cancel_late(self):
        return self.env.user.has_group(ADVANCE_CANCEL_AFTER_DAY_GROUP)

    @api.model
    def _advance_creation_day(self, record):
        """Fecha local (calendario) del create_date del registro."""
        if not record or not record.create_date:
            return fields.Date.context_today(self)
        local_dt = fields.Datetime.context_timestamp(record, record.create_date)
        return local_dt.date()

    @api.model
    def _advance_is_past_creation_day(self, record):
        if not record or not record.create_date:
            return False
        creation_day = self._advance_creation_day(record)
        today = fields.Date.context_today(record)
        return today > creation_day

    @api.model
    def _advance_cancel_allowed_for_record(self, record):
        if not record:
            return True
        if not self._advance_is_past_creation_day(record):
            return True
        return self._advance_user_can_cancel_late()

    @api.model
    def _advance_check_cancel_allowed(self, records, operation_label):
        """Bloquea cancelación/reversión después del día de create_date."""
        blocked = records.filtered(
            lambda r: not self._advance_cancel_allowed_for_record(r)
        )
        if not blocked:
            return
        names = ', '.join(blocked[:5].mapped('display_name'))
        if len(blocked) > 5:
            names = _('%s y %s más') % (names, len(blocked) - 5)
        raise UserError(_(
            'No puede %(operation)s el documento «%(names)s» porque ya pasó '
            'la medianoche del día en que fue creado. '
            'Se requiere el permiso «Cancelar después del día de creación» '
            'en Anticipos.',
            operation=operation_label,
            names=names,
        ))
