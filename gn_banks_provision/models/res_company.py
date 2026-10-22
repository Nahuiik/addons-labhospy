# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def write(self, vals):
        res = super().write(vals)
        if {'banks_accrual_provision_journal_id', 'banks_fx_differential_journal_id'} & vals.keys():
            self.env['bank.provision.sequence.helper'].ensure_company_provision_sequences(self)
        return res

    banks_accrual_provision_journal_id = fields.Many2one(
        'account.journal',
        string='Diario devengo / provisiones (predeterminado)',
        domain="[('company_id', '=', id), ('type', '=', 'general')]",
        check_company=True,
        help='Diario misceláneo sugerido al crear provisiones tipo «Devengo / provisión». '
             'El usuario puede cambiarlo en el documento. Si se deja vacío, se busca por nombre «Provisiones».',
    )
    banks_fx_differential_journal_id = fields.Many2one(
        'account.journal',
        string='Diario diferencial cambiario (provisiones)',
        domain="[('company_id', '=', id), ('type', 'in', ('bank', 'general'))]",
        check_company=True,
        help='Diario único permitido para documentos Provisiones con tipo «Diferencial cambiario». '
             'Si se deja vacío, el sistema usará el diario cuyo nombre sea exactamente «Diferencia de cambio».',
    )
