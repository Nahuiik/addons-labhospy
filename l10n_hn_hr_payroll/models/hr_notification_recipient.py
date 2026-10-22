# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models


class HrNotificationRecipient(models.Model):
    _name = 'hr.notification.recipient'
    _description = 'Destinatario de notificaciones RRHH'
    _order = 'user_id, notification_type'

    NOTIFICATION_TYPES = [
        ('contract_expiring', 'Contrato por vencer'),
        ('work_permit_expiring', 'Permiso de trabajo por vencer'),
        ('payroll_audit', 'Auditoría de nómina'),
        ('personal_info_change', 'Cambios en datos personales'),
    ]

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Usuario',
        required=True,
        domain=[('active', '=', True)],
    )
    notification_type = fields.Selection(
        NOTIFICATION_TYPES,
        string='Tipo de notificación',
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    _unique_user_type_company = models.Constraint(
        'UNIQUE(user_id, notification_type, company_id)',
        'Este usuario ya está configurado para recibir este tipo de notificación en esta compañía.',
    )

    @api.model
    def get_recipient_user_ids(self, company_id, notification_type):
        """
        Devuelve lista de user_ids configurados para recibir el tipo de notificación
        en la compañía indicada.

        :param company_id: int o record de res.company
        :param notification_type: str (contract_expiring, work_permit_expiring, payroll_audit, personal_info_change)
        :return: list of user ids
        """
        if not company_id:
            return []
        cid = company_id if isinstance(company_id, int) else company_id.id
        recs = self.search([
            ('company_id', '=', cid),
            ('notification_type', '=', notification_type),
        ], order='id')
        return recs.mapped('user_id').ids
