# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import _, api, fields, models


class GnCollectiveVacationResultLine(models.TransientModel):
    _name = 'gn.collective.vacation.result.line'
    _description = 'Línea resultado vacaciones colectivas'
    _order = 'state desc, employee_id'

    wizard_id = fields.Many2one(
        'gn.collective.vacation.result.wizard',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    state = fields.Selection(
        [('ok', 'Creado'), ('error', 'Error / omitido')],
        string='Resultado',
        required=True,
    )
    leave_id = fields.Many2one('hr.leave', string='Ausencia')
    number_of_days = fields.Float(string='Días')
    error_message = fields.Text(string='Detalle')


class GnCollectiveVacationResultWizard(models.TransientModel):
    _name = 'gn.collective.vacation.result.wizard'
    _description = 'Reporte resultado vacaciones colectivas'

    name = fields.Char(string='Referencia', default='Resultado vacaciones colectivas')
    source_wizard_note = fields.Text(string='Notas')
    line_ids = fields.One2many(
        'gn.collective.vacation.result.line',
        'wizard_id',
        string='Detalle por empleado',
    )
    count_ok = fields.Integer(string='Creados', compute='_compute_counts')
    count_err = fields.Integer(string='Errores u omitidos', compute='_compute_counts')

    @api.depends('line_ids', 'line_ids.state')
    def _compute_counts(self):
        for wiz in self:
            wiz.count_ok = len(wiz.line_ids.filtered(lambda l: l.state == 'ok'))
            wiz.count_err = len(wiz.line_ids.filtered(lambda l: l.state == 'error'))

    def action_open_created_leaves(self):
        self.ensure_one()
        ids = self.line_ids.filtered(lambda l: l.leave_id).mapped('leave_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ausencias generadas'),
            'res_model': 'hr.leave',
            'view_mode': 'list,form',
            'domain': [('id', 'in', ids)] if ids else [('id', '=', False)],
        }
