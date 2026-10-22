# -*- coding: utf-8 -*-
from odoo import api, fields, models


class GnHrPortalAuditLog(models.Model):
    _name = 'gn.hr.portal.audit.log'
    _description = 'Registro de auditoría del portal de empleados'
    _order = 'timestamp desc'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    user_id = fields.Many2one('res.users', string='Usuario', required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    action = fields.Char(string='Acción', required=True)
    model = fields.Char(string='Modelo')
    res_id = fields.Integer(string='ID Registro')
    timestamp = fields.Datetime(string='Fecha/Hora', default=fields.Datetime.now, required=True)
    ip = fields.Char(string='IP')
    user_agent = fields.Char(string='User Agent')

    @api.model
    def log_action(self, action, model=None, res_id=None, employee_id=None, **kwargs):
        """Registra una acción en el log de auditoría."""
        user = self.env.user
        if user._is_public():
            return
        request = getattr(self.env, 'request', None)
        ip = user_agent = None
        if request and hasattr(request, 'httprequest'):
            ip = request.httprequest.remote_addr
            user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')[:500]
        company_id = kwargs.get('company_id')
        emp_id = employee_id or kwargs.get('employee_id')
        if not company_id and emp_id:
            emp = self.env['hr.employee'].browse(emp_id)
            if emp:
                company_id = emp.company_id.id
        if not company_id:
            company_id = self.env.company.id
        vals = {
            'user_id': user.id,
            'employee_id': emp_id,
            'company_id': company_id,
            'action': action,
            'model': model,
            'res_id': res_id,
            'ip': ip,
            'user_agent': user_agent,
        }
        return self.sudo().create(vals)
