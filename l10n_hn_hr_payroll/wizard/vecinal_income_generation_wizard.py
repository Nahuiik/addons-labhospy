# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VecinalIncomeGenerationWizard(models.TransientModel):
    """Wizard to generate employee income records for active employees"""
    _name = 'l10n.hn.vecinal.income_generation_wizard'
    _description = 'Generate Employee Income Records Wizard'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                default=lambda self: self.env.company)
    year_base = fields.Integer(string='Base Year', required=True,
                              default=lambda self: fields.Date.today().year - 1,
                              help='Year of the income (e.g., 2025 if applying in 2026)')
    
    def action_generate(self):
        """Generate income records for active employees"""
        self.ensure_one()
        return self.env['l10n.hn.vecinal.employee_income'].generate_for_active_employees(
            self.company_id.id, self.year_base
        )
