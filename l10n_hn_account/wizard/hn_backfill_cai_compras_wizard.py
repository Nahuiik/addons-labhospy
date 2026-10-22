# -*- coding: utf-8 -*-
from odoo import fields, models


class HnBackfillCaiComprasWizard(models.TransientModel):
    _name = 'hn.backfill.cai.compras.wizard'
    _description = 'Rellenar CAI compras en facturas de proveedor publicadas'

    company_ids = fields.Many2many(
        'res.company',
        string='Compañías',
        required=True,
        default=lambda self: [(6, 0, self.env.companies.ids)],
        help='Solo facturas de proveedor pertenecientes a estas compañías.',
    )
    invoice_date_from = fields.Date(string='Fecha factura proveedor desde (opc.)')
    invoice_date_to = fields.Date(string='Fecha factura proveedor hasta (opc.)')

    def action_run_backfill(self):
        self.ensure_one()
        domain = [
            ('state', '=', 'posted'),
            ('move_type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
            ('company_id', 'in', self.company_ids.ids),
            '|',
            ('cai_shot_compras', '=', False),
            ('cai_shot_compras', '=', ''),
        ]
        if self.invoice_date_from:
            domain.append(('invoice_date', '>=', self.invoice_date_from))
        if self.invoice_date_to:
            domain.append(('invoice_date', '<=', self.invoice_date_to))
        moves = self.env['account.move'].search(domain, order='id')
        Move = self.env['account.move']
        result = Move._l10n_hn_backfill_cai_shot_compras_run(moves)
        return Move._l10n_hn_backfill_cai_client_notification(result)
