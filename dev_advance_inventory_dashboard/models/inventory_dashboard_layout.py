# -*- coding: utf-8 -*-
"""Persistencia de layouts configurables por usuario."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

DEFAULT_WIDGETS = [
    'executive_header', 'executive_kpis', 'hero_chart', 'alerts_insights',
    'financial', 'advanced_charts', 'activity', 'quick_actions', 'tables',
]

DEFAULT_LAYOUT = {
    'widgets': [
        {'id': wid, 'type': wid, 'visible': True, 'size': 'full', 'order': i}
        for i, wid in enumerate(DEFAULT_WIDGETS)
    ],
    'kpi_keys': [],
    'chart_keys': [],
    'refresh_minutes': 0,
    'dark_mode': False,
}


class InventoryDashboardLayout(models.Model):
    _name = 'inventory.dashboard.layout'
    _description = 'Inventory Dashboard User Layout'
    _order = 'is_default desc, name, id'

    name = fields.Char(string='Nombre', required=True, default=lambda self: _('Predeterminado'))
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    is_default = fields.Boolean(string='Predeterminado', default=False)
    layout_json = fields.Json(string='Layout', default=lambda: DEFAULT_LAYOUT)

    _sql_constraints = [
        ('user_name_uniq', 'unique(user_id, name)', 'Ya existe un layout con ese nombre.'),
    ]

    @api.model
    def _check_layout_access(self):
        if not self.env.user.has_group(
            'dev_advance_inventory_dashboard.group_allow_access_inventory'
        ):
            raise UserError(_('No tiene permiso para acceder al Dashboard de Inventario.'))

    @api.model
    def get_layouts(self):
        self._check_layout_access()
        rows = self.search([('user_id', '=', self.env.uid)])
        if not rows:
            default = self.create({
                'user_id': self.env.uid,
                'name': _('Predeterminado'),
                'is_default': True,
                'layout_json': DEFAULT_LAYOUT,
            })
            rows = default
        return [{
            'id': r.id,
            'name': r.name,
            'is_default': r.is_default,
            'layout': r.layout_json or DEFAULT_LAYOUT,
        } for r in rows]

    @api.model
    def save_layout(self, layout_id, name, layout_json, is_default=False):
        self._check_layout_access()
        vals = {'name': name, 'layout_json': layout_json}
        if is_default:
            self.search([('user_id', '=', self.env.uid)]).write({'is_default': False})
            vals['is_default'] = True
        if layout_id:
            rec = self.browse(layout_id)
            if rec.user_id.id != self.env.uid:
                raise UserError(_('No puede modificar layouts de otro usuario.'))
            rec.write(vals)
            return rec.id
        vals['user_id'] = self.env.uid
        if is_default or not self.search_count([('user_id', '=', self.env.uid)]):
            vals.setdefault('is_default', True)
        return self.create(vals).id

    @api.model
    def reset_layout(self, layout_id=None):
        self._check_layout_access()
        domain = [('user_id', '=', self.env.uid)]
        if layout_id:
            domain.append(('id', '=', layout_id))
        rows = self.search(domain)
        rows.write({'layout_json': DEFAULT_LAYOUT})
        return True
