# -*- coding: utf-8 -*-
from odoo import models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_open_portal_invite_wizard(self):
        self.ensure_one()
        wizard = self.env['gn.hr.employee.portal.invite.wizard'].create({
            'employee_id': self.id,
        })
        return wizard._action_open_modal()
