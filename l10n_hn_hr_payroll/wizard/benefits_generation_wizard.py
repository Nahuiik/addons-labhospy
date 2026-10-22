# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _


class BenefitsGenerationWizard(models.TransientModel):
    """Wizard to generate 13th and 14th month benefits for all employees"""
    _name = 'l10n.hn.benefits.generation.wizard'
    _description = 'Benefits Generation Wizard'
    
    benefit_type = fields.Selection([
        ('thirteenth', '13th Month (Aguinaldo)'),
        ('fourteenth', '14th Month'),
    ], string='Benefit Type', required=True, default='thirteenth')
    
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    
    def action_generate(self):
        """Generate benefits for all employees"""
        self.ensure_one()
        
        if self.benefit_type == 'thirteenth':
            model = self.env['l10n.hn.thirteenth.month']
        else:
            model = self.env['l10n.hn.fourteenth.month']
        
        result = model.generate_for_all_employees(self.year)
        
        message = _('Proceso completado:\n\n')
        message += _('- Registros creados: %d\n') % result['created']
        message += _('- Registros actualizados: %d\n') % result['updated']
        message += _('- Total de empleados procesados: %d') % result['total']
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cálculo de %s') % ('13° Mes' if self.benefit_type == 'thirteenth' else '14° Mes'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
