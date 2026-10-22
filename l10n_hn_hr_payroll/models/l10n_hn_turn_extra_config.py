# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nHnTurnExtraConfig(models.Model):
    """Configuración de factores de multiplicación para Turnos Extra (TE)"""
    _name = 'l10n.hn.turn.extra.config'
    _description = 'Configuración Turnos Extra'
    _order = 'company_id'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
    )
    turn_a_factor = fields.Float(
        string='Recargo Turno A',
        digits=(6, 4),
        default=1.0,
        help='Recargo del turno A. TE = (Días por turno) × (Sueldo diario) × Recargo. 1.0 = sin recargo.',
    )
    turn_b_factor = fields.Float(
        string='Recargo Turno B',
        digits=(6, 4),
        default=1.0,
        help='Recargo del turno B. TE = (Días por turno) × (Sueldo diario) × Recargo. 1.0 = sin recargo.',
    )
    turn_c_factor = fields.Float(
        string='Recargo Turno C',
        digits=(6, 4),
        default=1.0,
        help='Recargo del turno C. TE = (Días por turno) × (Sueldo diario) × Recargo. 1.0 = sin recargo.',
    )

    _company_unique = models.Constraint(
        'UNIQUE(company_id)',
        'Solo puede haber una configuración de turnos extra por compañía.',
    )

    @api.constrains('turn_a_factor', 'turn_b_factor', 'turn_c_factor')
    def _check_factors(self):
        for rec in self:
            for fname, fval in [('turn_a_factor', rec.turn_a_factor),
                               ('turn_b_factor', rec.turn_b_factor),
                               ('turn_c_factor', rec.turn_c_factor)]:
                if fval < 0:
                    raise ValidationError(_('Los factores no pueden ser negativos.'))

    @api.model
    def get_factors(self, company_id=None):
        """
        Obtiene los factores para Turnos Extra de la compañía.
        Retorna (factor_a, factor_b, factor_c). Si no hay config, retorna (1.0, 1.0, 1.0).
        """
        company = company_id or self.env.company
        config = self.search([('company_id', '=', company.id)], limit=1)
        if not config:
            return 1.0, 1.0, 1.0
        return config.turn_a_factor, config.turn_b_factor, config.turn_c_factor
