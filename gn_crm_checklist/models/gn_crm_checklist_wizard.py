# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class GnCrmChecklistWizard(models.TransientModel):
    _name = 'gn.crm.checklist.wizard'
    _description = 'Wizard para Agregar Checklist a Lead'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead/Oportunidad',
        required=True,
    )
    checklist_id = fields.Many2one(
        'gn.crm.checklist',
        string='Checklist',
        required=True,
        domain=[('active', '=', True)],
    )

    def action_add_checklist(self):
        """Agregar checklist al lead"""
        self.ensure_one()
        lead = self.lead_id
        checklist = self.checklist_id

        # Verificar si el checklist ya está agregado
        if checklist in lead.checklist_ids:
            raise UserError(_('Este checklist ya está agregado al lead.'))

        # Agregar el checklist
        lead.write({
            'checklist_ids': [(4, checklist.id)],
        })

        # Crear las líneas de checklist para cada item
        for item in checklist.item_ids:
            self.env['gn.crm.checklist.line'].create({
                'lead_id': lead.id,
                'checklist_id': checklist.id,
                'item_id': item.id,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito'),
                'message': _('Checklist agregado correctamente.'),
                'type': 'success',
                'sticky': False,
            },
        }


