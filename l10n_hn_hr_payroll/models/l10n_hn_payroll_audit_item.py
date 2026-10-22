# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models


class L10nHnPayrollAuditItem(models.Model):
    _name = 'l10n.hn.payroll.audit.item'
    _description = 'Item de Auditoría de Nómina'
    _order = 'sequence, id'

    audit_run_id = fields.Many2one(
        comodel_name='l10n.hn.payroll.audit.run',
        string='Proceso de auditoría',
        ondelete='cascade',
        index=True,
    )
    audit_type = fields.Selection(
        [
            ('monthly', 'Mensual'),
            ('annual', 'Anual'),
        ],
        string='Tipo (plantilla)',
        help='Solo para items plantilla. Define a qué tipo de auditoría pertenece.',
    )
    name = fields.Char(
        string='Descripción',
        required=True,
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )
    action_id = fields.Many2one(
        comodel_name='ir.actions.act_window',
        string='Acción',
        help='Acción a abrir al hacer clic en el enlace.',
    )
    is_done = fields.Boolean(
        string='Completado',
        default=False,
    )
    notes = fields.Text(
        string='Notas',
    )

    def action_open(self):
        """Abre la acción asociada si existe."""
        self.ensure_one()
        if self.action_id:
            return self.action_id.read()[0]
        return False
