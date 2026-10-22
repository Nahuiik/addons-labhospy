# -*- coding: utf-8 -*-
"""Preferencias personales del Tablero Financiero por usuario.

Cada usuario puede personalizar qué pestañas y secciones ve y en qué orden,
sin afectar la configuración base de la compañía (gn.financial.dashboard.config).

Si un usuario no tiene preferencia para una sección, hereda la visibilidad
y el orden de la configuración de compañía.
"""
from odoo import api, fields, models

from .dashboard_config import SECTION_KEYS


# Pestañas adicionales (no en SECTION_KEYS) que el usuario puede ocultar.
TAB_KEYS = ('overview',)


# Todas las claves que el usuario puede personalizar.
ALL_PREF_KEYS = TAB_KEYS + SECTION_KEYS


class GnFinancialDashboardUserPref(models.Model):
    _name = 'gn.financial.dashboard.user.pref'
    _description = 'Preferencias personales del Tablero Financiero'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        'res.users', string='Usuario', required=True,
        default=lambda self: self.env.user, index=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company, index=True,
        ondelete='cascade',
    )

    # Visibilidad por sección/pestaña (cada usuario decide qué quiere ver).
    show_overview = fields.Boolean(string='Resumen', default=True)
    show_profitability = fields.Boolean(string='Rentabilidad', default=True)
    show_liquidity = fields.Boolean(string='Liquidez y balance', default=True)
    show_cashflow = fields.Boolean(string='Flujo de caja', default=True)
    show_aging = fields.Boolean(string='Cartera por antigüedad', default=True)
    show_expense_ranking = fields.Boolean(string='Ranking de gastos', default=True)
    show_partner_ranking = fields.Boolean(string='Ranking de terceros', default=True)
    show_analysis = fields.Boolean(string='Análisis automático', default=True)
    show_data_quality = fields.Boolean(string='Calidad de datos', default=True)

    # Orden personalizado (menor = primero). Si es 0, hereda del config.
    seq_overview = fields.Integer(string='Orden resumen', default=0)
    seq_profitability = fields.Integer(string='Orden rentabilidad', default=0)
    seq_liquidity = fields.Integer(string='Orden liquidez', default=0)
    seq_cashflow = fields.Integer(string='Orden flujo de caja', default=0)
    seq_aging = fields.Integer(string='Orden cartera', default=0)
    seq_expense_ranking = fields.Integer(string='Orden ranking gastos', default=0)
    seq_partner_ranking = fields.Integer(string='Orden ranking terceros', default=0)
    seq_analysis = fields.Integer(string='Orden análisis', default=0)
    seq_data_quality = fields.Integer(string='Orden calidad de datos', default=0)

    # Otras preferencias visuales por usuario.
    compact_mode = fields.Boolean(string='Modo compacto', default=False)

    _user_company_uniq = models.Constraint(
        'unique(user_id, company_id)',
        'El usuario ya tiene preferencias para esta compañía.',
    )

    @api.model
    def get_or_create_for(self, user=None, company=None):
        """Devuelve (creando si hace falta) las preferencias del usuario y compañía dados."""
        user = user or self.env.user
        company = company or self.env.company
        pref = self.sudo().search([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if not pref:
            pref = self.sudo().create({
                'user_id': user.id,
                'company_id': company.id,
            })
        return pref

    def apply_to_payload(self, base_payload):
        """Fusiona estas preferencias sobre el payload de la config de compañía.

        ``base_payload`` viene de :meth:`gn.financial.dashboard.config.to_payload`.
        Las preferencias del usuario pueden ocultar/reordenar secciones, pero
        nunca habilitar una sección que la compañía haya desactivado.
        """
        self.ensure_one()
        out = dict(base_payload or {})
        out['sections'] = self._merge_sections(out.get('sections') or [])
        out['tabs'] = self._tab_payload()
        out['theme'] = dict(out.get('theme') or {})
        # Modo compacto: el usuario puede activar el suyo independientemente.
        if self.compact_mode:
            out['theme']['compact_mode'] = True
        out['user_pref'] = {
            'id': self.id,
            'compact_mode': self.compact_mode,
        }
        return out

    def _merge_sections(self, base_sections):
        """Aplica visibilidad y orden personalizados sobre las secciones."""
        merged = []
        for sec in base_sections:
            key = sec['key']
            # AND lógico: una sección solo es visible si ambos lo permiten.
            user_visible = bool(self['show_%s' % key]) if hasattr(self, 'show_%s' % key) else True
            user_seq = self['seq_%s' % key] if hasattr(self, 'seq_%s' % key) else 0
            merged.append({
                'key': key,
                'visible': sec['visible'] and user_visible,
                'sequence': user_seq if user_seq else sec['sequence'],
            })
        merged.sort(key=lambda s: s['sequence'])
        return merged

    def _tab_payload(self):
        """Visibilidad y orden de las pestañas no asociadas a SECTION_KEYS
        (hoy solo ``overview``)."""
        return [
            {
                'key': key,
                'visible': bool(self['show_%s' % key]),
                'sequence': self['seq_%s' % key] or 0,
            }
            for key in TAB_KEYS
        ]
