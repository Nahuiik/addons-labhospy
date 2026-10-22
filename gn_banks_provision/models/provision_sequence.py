# -*- coding: utf-8 -*-
from odoo import _, api, models

PROVISION_SEQUENCE_PREFIX = 'PRO-%(year)s-%(month)s-%(day)s-'
FX_DIFFERENTIAL_SEQUENCE_PREFIX = 'DC-%(year)s-%(month)s-%(day)s-'
PROVISION_SEQUENCE_PADDING = 5


class BankProvisionSequenceHelper(models.AbstractModel):
    _name = 'bank.provision.sequence.helper'
    _description = 'Secuencias predeterminadas de provisiones bancarias'

    @api.model
    def _sequence_specs(self):
        return {
            'provision': {
                'name': _('Provisionamiento'),
                'prefix': PROVISION_SEQUENCE_PREFIX,
                'padding': PROVISION_SEQUENCE_PADDING,
            },
            'fx_differential': {
                'name': _('Diferencial cambiario'),
                'prefix': FX_DIFFERENTIAL_SEQUENCE_PREFIX,
                'padding': PROVISION_SEQUENCE_PADDING,
            },
        }

    @api.model
    def ensure_journal_sequence(self, journal, move_type):
        """Crea o actualiza la secuencia del diario con el formato estándar."""
        if not journal or move_type not in self._sequence_specs():
            return self.env['ir.sequence']
        spec = self._sequence_specs()[move_type]
        # SUDO-JUSTIFIED: crear/actualizar secuencias técnicas por diario en post_init y write
        Sequence = self.env['ir.sequence'].sudo()
        seq = Sequence.search([
            ('journal_id', '=', journal.id),
            ('move_type', '=', move_type),
        ], limit=1)
        vals = {
            'name': spec['name'],
            'prefix': spec['prefix'],
            'padding': spec['padding'],
            'company_id': journal.company_id.id,
            'journal_id': journal.id,
            'move_type': move_type,
            'implementation': 'standard',
        }
        if seq:
            seq.write({
                'name': vals['name'],
                'prefix': vals['prefix'],
                'padding': vals['padding'],
            })
        else:
            seq = Sequence.create(vals)
        return seq

    @api.model
    def ensure_company_provision_sequences(self, company):
        """Asegura secuencias en los diarios configurados (o fallback por nombre)."""
        Provision = self.env['bank.provision']
        accrual_journal = Provision._get_company_accrual_provision_journal(company)
        if accrual_journal:
            self.ensure_journal_sequence(accrual_journal, 'provision')
        fx_journal = Provision._get_company_fx_differential_journal(company)
        if fx_journal:
            self.ensure_journal_sequence(fx_journal, 'fx_differential')
