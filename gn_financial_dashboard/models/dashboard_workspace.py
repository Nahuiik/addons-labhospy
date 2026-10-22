# -*- coding: utf-8 -*-
"""Espacios de trabajo del Tablero Financiero (V20 Fase 2, #2 + #20).

Un *workspace* es una vista personalizada del tablero: layout de pestañas y
secciones visibles, KPIs personalizados destacados y orden. Cada usuario tiene
sus workspaces; opcionalmente puede compartirse con toda la compañía como un
preset que cualquiera puede aplicar.

El layout es un JSON simple que el frontend interpreta y que contiene:
``sections`` (lista de secciones con ``key``, ``visible`` y ``sequence``),
``tabs_order`` (orden de pestañas) y ``featured_kpis`` (ids de KPIs
personalizados destacados en el resumen).
"""
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class GnFinancialDashboardWorkspace(models.Model):
    _name = 'gn.financial.dashboard.workspace'
    _description = 'Espacio de trabajo del Tablero Financiero'
    _order = 'is_default desc, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    description = fields.Text(string='Descripción')
    user_id = fields.Many2one(
        'res.users', string='Propietario', required=True,
        default=lambda self: self.env.user, ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
    )
    shared = fields.Boolean(
        string='Compartido con la compañía',
        default=False,
        help='Si está activo, otros usuarios de la misma compañía pueden usar '
             'este workspace como preset (sin modificarlo).',
    )
    is_default = fields.Boolean(
        string='Predeterminado',
        default=False,
        help='Marca el workspace que se carga al abrir el tablero. Solo uno '
             'por usuario.',
    )
    layout_json = fields.Text(
        string='Layout (JSON)',
        default='{}',
        help='Estructura JSON con secciones, orden de pestañas y KPIs '
             'destacados. Editado desde el tablero (UI).',
    )

    _user_name_uniq = models.Constraint(
        'unique(user_id, name)',
        'Ya tienes un espacio de trabajo con ese nombre.',
    )

    @api.model
    def get_or_create_default_for(self, user, company):
        """Devuelve el workspace por defecto del usuario (lo crea si no existe)."""
        ws = self.search([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
            ('is_default', '=', True),
        ], limit=1)
        if ws:
            return ws
        return self.create({
            'name': _('Mi tablero'),
            'user_id': user.id,
            'company_id': company.id,
            'is_default': True,
            'layout_json': '{}',
        })

    def write(self, vals):
        """Si se marca uno como predeterminado, desmarca los demás del mismo usuario."""
        res = super().write(vals)
        if vals.get('is_default'):
            for rec in self:
                others = self.search([
                    ('user_id', '=', rec.user_id.id),
                    ('company_id', '=', rec.company_id.id),
                    ('id', '!=', rec.id),
                    ('is_default', '=', True),
                ])
                if others:
                    others.write({'is_default': False})
        return res

    def _layout(self):
        """Decodifica ``layout_json`` con tolerancia a errores."""
        self.ensure_one()
        if not (self.layout_json or '').strip():
            return {}
        try:
            return json.loads(self.layout_json)
        except (TypeError, ValueError):
            return {}

    def to_payload(self):
        """Serializa el workspace para el frontend."""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'is_default': self.is_default,
            'shared': self.shared,
            'owner_id': self.user_id.id,
            'owner_name': self.user_id.display_name,
            'layout': self._layout(),
        }

    def set_layout(self, layout):
        """Guarda el layout (dict serializable)."""
        self.ensure_one()
        if not isinstance(layout, dict):
            raise UserError(_('El layout debe ser un objeto JSON.'))
        self.layout_json = json.dumps(layout, ensure_ascii=False, sort_keys=True)
        return True
