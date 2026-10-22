# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

import json

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    hn_vac_payroll_settlement_json = fields.Text(
        string='Liquidación vacaciones nómina (técnico)',
        copy=False,
        groups='l10n_hn_hr_payroll.group_hr_payroll_user',
    )

    @api.depends('line_ids.total', 'struct_id.rule_ids.appears_on_employee_cost_dashboard', 'struct_id.hn_vacation_payroll_kind')
    def _compute_basic_net(self):
        vacation = self.filtered(lambda p: p.struct_id.hn_vacation_payroll_kind)
        super(HrPayslip, self - vacation)._compute_basic_net()
        if not vacation:
            return
        employer_cost_codes = set(self.env['hr.salary.rule'].search([
            ('appears_on_employee_cost_dashboard', '=', True),
        ]).mapped('code'))
        employer_cost_values = (
            vacation._origin._get_line_values(employer_cost_codes) if employer_cost_codes else {}
        )
        vac_line_values = vacation._origin._get_line_values(['HN_VAC_PAY'])
        for payslip in vacation:
            employer_cost_total = 0.0
            payslip_employer_codes = payslip.struct_id.rule_ids.filtered(
                'appears_on_employee_cost_dashboard'
            ).mapped('code')
            for code in payslip_employer_codes:
                employer_cost_total += employer_cost_values[code][payslip._origin.id]['total']
            pay = vac_line_values['HN_VAC_PAY'][payslip._origin.id]['total']
            payslip.write({
                'basic_wage': 0.0,
                'gross_wage': pay,
                'net_wage': pay,
                'employer_cost': employer_cost_total,
            })

    def _hn_vacation_payroll_settlement_revert(self):
        Allocation = self.env['hr.leave.allocation']
        for slip in self:
            if not slip.struct_id.hn_vacation_payroll_kind:
                continue
            data = slip.hn_vac_payroll_settlement_json
            if not data:
                continue
            try:
                rows = json.loads(data)
            except json.JSONDecodeError:
                slip.hn_vac_payroll_settlement_json = False
                continue
            for row in rows:
                alloc = Allocation.browse(row.get('allocation_id'))
                if alloc.exists():
                    prev = alloc.hn_vac_payroll_settled_days or 0.0
                    alloc.hn_vac_payroll_settled_days = max(0.0, prev - row.get('days', 0))
            slip.hn_vac_payroll_settlement_json = False

    def _hn_vacation_payroll_settlement_apply(self):
        for slip in self:
            if not slip.struct_id.hn_vacation_payroll_kind:
                continue
            if slip.hn_vac_payroll_settlement_json:
                continue
            days = slip.employee_id._hn_vacation_payroll_payable_days(slip)
            if days <= 0:
                continue
            applied = slip.employee_id._hn_vacation_payroll_settle_allocations(days)
            slip.hn_vac_payroll_settlement_json = json.dumps(applied)

    def action_payslip_done(self):
        res = super().action_payslip_done()
        self.filtered(lambda s: s.struct_id.hn_vacation_payroll_kind)._hn_vacation_payroll_settlement_apply()
        return res

    def action_payslip_draft(self):
        self.filtered(lambda s: s.struct_id.hn_vacation_payroll_kind)._hn_vacation_payroll_settlement_revert()
        return super().action_payslip_draft()

    def action_payslip_cancel(self):
        self.filtered(
            lambda s: s.struct_id.hn_vacation_payroll_kind and s.state == 'validated'
        )._hn_vacation_payroll_settlement_revert()
        return super().action_payslip_cancel()
