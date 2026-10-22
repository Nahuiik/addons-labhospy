# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    @api.model
    def _gn_hr_sanitize_version_write_vals(self, vals):
        """date_version es NOT NULL; el flush (_write_multi) y write() no deben enviar NULL."""
        if not vals:
            return vals
        vals = dict(vals)
        if 'date_version' in vals and not vals['date_version']:
            vals.pop('date_version')
        return vals

    def write(self, vals):
        vals = self._gn_hr_sanitize_version_write_vals(vals)
        return super().write(vals)

    def _write_multi(self, vals_list):
        vals_list = [self._gn_hr_sanitize_version_write_vals(v) for v in vals_list]
        super()._write_multi(vals_list)

    payroll_structure_id = fields.Many2one(
        'hr.payroll.structure',
        string='Estructura salarial',
        related='structure_type_id.default_struct_id',
        readonly=True,
    )
    structure_type_country_id = fields.Many2one(
        'res.country',
        string='País (tipo de estructura)',
        related='structure_type_id.country_id',
        readonly=True,
    )
