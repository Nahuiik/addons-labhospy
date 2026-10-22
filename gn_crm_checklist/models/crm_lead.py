# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    checklist_ids = fields.Many2many(
        'gn.crm.checklist',
        'crm_lead_checklist_rel',
        'lead_id',
        'checklist_id',
        string='Checklists',
        copy=False,
    )
    checklist_line_ids = fields.One2many(
        'gn.crm.checklist.line',
        'lead_id',
        string='Líneas de Checklist',
        copy=False,
    )
    checklist_progress = fields.Float(
        string='Progreso del Checklist (%)',
        compute='_compute_checklist_progress',
        store=True,
        help='Porcentaje de progreso basado en items completados',
    )

    @api.depends('checklist_line_ids', 'checklist_line_ids.is_completed')
    def _compute_checklist_progress(self):
        for lead in self:
            total_items = len(lead.checklist_line_ids)
            if total_items == 0:
                lead.checklist_progress = 0.0
            else:
                completed_items = len(lead.checklist_line_ids.filtered('is_completed'))
                lead.checklist_progress = (completed_items / total_items) * 100.0

    def action_add_checklist(self):
        """Abrir wizard para agregar checklist"""
        self.ensure_one()
        return {
            'name': _('Agregar Checklist'),
            'type': 'ir.actions.act_window',
            'res_model': 'gn.crm.checklist.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
            },
        }

    def action_complete_checklist(self):
        """Completar todos los items del checklist"""
        self.ensure_one()
        if not self.env.user.has_group('gn_crm_checklist.group_crm_checklist_user'):
            raise UserError(_('No tiene permisos para completar checklists.'))
        self.checklist_line_ids.write({'is_completed': True})
        return True

    def action_cancel_checklist(self):
        """Cancelar todos los items del checklist"""
        self.ensure_one()
        if not self.env.user.has_group('gn_crm_checklist.group_crm_checklist_user'):
            raise UserError(_('No tiene permisos para cancelar checklists.'))
        self.checklist_line_ids.write({'is_completed': False})
        return True


class GnCrmChecklistLine(models.Model):
    _name = 'gn.crm.checklist.line'
    _description = 'CRM Checklist Line'
    _order = 'sequence, id'
    _rec_name = 'name'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead/Oportunidad',
        required=True,
        ondelete='cascade',
        index=True,
    )
    checklist_id = fields.Many2one(
        'gn.crm.checklist',
        string='Checklist',
        required=True,
    )
    item_id = fields.Many2one(
        'gn.crm.checklist.item',
        string='Item',
        required=True,
    )
    name = fields.Char(
        string='Nombre',
        related='item_id.name',
        store=True,
    )
    sequence = fields.Integer(
        string='Secuencia',
        related='item_id.sequence',
        store=True,
    )
    is_completed = fields.Boolean(
        string='Completado',
        default=False,
    )
    completed_date = fields.Datetime(
        string='Fecha de Completado',
        readonly=True,
    )
    completed_by = fields.Many2one(
        'res.users',
        string='Completado por',
        readonly=True,
    )

    def action_toggle_complete(self):
        """Alternar estado de completado"""
        self.ensure_one()
        if not self.env.user.has_group('gn_crm_checklist.group_crm_checklist_user'):
            raise UserError(_('No tiene permisos para completar/cancelar items del checklist.'))
        self.is_completed = not self.is_completed
        if self.is_completed:
            self.completed_date = fields.Datetime.now()
            self.completed_by = self.env.user
        else:
            self.completed_date = False
            self.completed_by = False

