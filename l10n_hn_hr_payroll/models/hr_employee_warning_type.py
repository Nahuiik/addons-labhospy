# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models


class HrEmployeeWarningType(models.Model):
    _name = 'hr.employee.warning.type'
    _description = 'Tipo de Alerta de Empleado'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(string='Código', required=True, index=True)
    description = fields.Text(string='Descripción', translate=True)
    active = fields.Boolean(string='Activo', default=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    icon = fields.Char(string='Icono (FontAwesome)', help='Ej: fa-file-o, fa-calendar')
    alert_style = fields.Selection([
        ('info', 'Información (Azul)'),
        ('warning', 'Advertencia (Amarillo)'),
        ('danger', 'Peligro (Rojo)'),
    ], string='Estilo de Alerta', default='warning')
    employee_field = fields.Char(
        string='Campo Booleano',
        help='Nombre del campo booleano en hr.employee que controla la visibilidad.',
    )
    config_hint = fields.Char(
        string='Configuración',
        help='Dónde se configura el parámetro de esta alerta.',
    )
    icon_preview = fields.Html(
        string='Icono',
        compute='_compute_icon_preview',
    )

    _STYLE_COLORS = {
        'info': '#17a2b8',
        'warning': '#e6a800',
        'danger': '#dc3545',
    }

    @api.depends('icon', 'alert_style')
    def _compute_icon_preview(self):
        for rec in self:
            if rec.icon:
                color = self._STYLE_COLORS.get(rec.alert_style, '#6c757d')
                rec.icon_preview = (
                    '<i class="fa %s" style="font-size:1.4em;color:%s;"/>'
                    % (rec.icon, color)
                )
            else:
                rec.icon_preview = False

    _code_uniq = models.Constraint(
        'UNIQUE(code)',
        'El código del tipo de alerta debe ser único.',
    )

    def _is_warning_active(self, code):
        """Retorna True si el warning con el código dado está activo (o no existe registro).
        Uses a request-level cache to avoid repeated search() calls."""
        cache_attr = '_warning_active_cache'
        if not hasattr(self.env, cache_attr):
            all_types = self.search([])
            setattr(self.env, cache_attr, {wt.code: wt.active for wt in all_types})
        cache = getattr(self.env, cache_attr)
        return cache.get(code, True)
