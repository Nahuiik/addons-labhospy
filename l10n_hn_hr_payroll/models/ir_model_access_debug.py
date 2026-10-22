# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik - Fix ACL for ISR calculation wizard

from odoo import api, models


class IrModelAccessDebug(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    def check(self, model, mode='read', raise_exception=True):
        if model == 'l10n.hn.isr.calculation.wizard':
            self._ensure_wizard_access_records()
        return super().check(model, mode=mode, raise_exception=raise_exception)

    def _ensure_wizard_access_records(self):
        """Create ir.model.access for wizard if missing (fallback when CSV/migration fail)."""
        exists = self.sudo().search([
            ('model_id.model', '=', 'l10n.hn.isr.calculation.wizard'),
        ], limit=1)
        if exists:
            return
        ir_model = self.env['ir.model'].sudo().search(
            [('model', '=', 'l10n.hn.isr.calculation.wizard')], limit=1
        )
        if not ir_model:
            return
        ref = self.env['ir.model.data'].sudo()._xmlid_to_res_id
        groups_map = [
            ('l10n_hn_hr_payroll.group_hr_payroll_admin', 'access_l10n_hn_isr_calculation_wizard_admin'),
            ('l10n_hn_hr_payroll.group_hr_payroll_user', 'access_l10n_hn_isr_calculation_wizard_user'),
            ('base.group_user', 'access_l10n_hn_isr_calculation_wizard_user_base'),
            ('base.group_system', 'access_l10n_hn_isr_calculation_wizard_system'),
        ]
        for group_xmlid, access_name in groups_map:
            try:
                gid = ref(group_xmlid, raise_if_not_found=False)
                if gid:
                    self.sudo().create({
                        'name': access_name,
                        'model_id': ir_model.id,
                        'group_id': gid,
                        'perm_read': True,
                        'perm_write': True,
                        'perm_create': True,
                        'perm_unlink': True,
                    })
            except Exception:
                pass
