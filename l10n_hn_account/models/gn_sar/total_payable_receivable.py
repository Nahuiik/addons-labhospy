from odoo import api, models, fields


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    partner_credit = fields.Monetary(compute='credit_debit_get',string='Customer Total Receivable', help="Total amount this customer owes you.")
    partner_debit = fields.Monetary(compute='credit_debit_get',string='Customer Total Payable',help="Total amount you have to pay to this vendor.")

    @api.depends_context('force_company')
    def credit_debit_get(self):
        ids = [partner.id for partner in self if partner._origin]
        if not ids:

            self.partner_debit = 0
            self.partner_debit = 0
            self.partner_credit = 0
            return
        aml_env = self.env['account.move.line'].with_context(
            state='posted',
            company_id=self.env.company.id,
        )
        domain = aml_env._build_coa_domain([
            ('partner_id', 'in', ids),
            ('reconciled', '=', False),
            ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
        ])
        groups = aml_env.read_group(
            domain,
            ['amount_residual:sum'],
            ['partner_id', 'account_id.account_type'],
        )
        result_map = {pid: {'asset_receivable': 0.0, 'liability_payable': 0.0} for pid in ids}
        for group in groups:
            partner = group.get('partner_id')
            if not partner:
                continue
            pid = partner[0]
            acc_type = group.get('account_id.account_type')
            if pid in result_map and acc_type in result_map[pid]:
                result_map[pid][acc_type] = group.get('amount_residual', 0.0)

        for partner in self:
            values = result_map.get(partner.id, {})
            receivable = values.get('asset_receivable', 0.0)
            payable = values.get('liability_payable', 0.0)
            partner.partner_credit = receivable or 0.0
            partner.partner_debit = -payable if payable else 0.0
