# -*- coding: utf-8 -*-
from odoo import models


def get_employee_from_user(env, user):
    """
    Obtiene el empleado asociado al usuario.
    - Preferir hr.employee donde user_id == user
    - Fallback: work_email == user.login (normalizado) y setear user_id si no está vinculado
    - Si no existe: retornar None
    """
    if not user or user._is_public():
        return env['hr.employee']
    # 1. Preferir user_id
    employee = env['hr.employee'].sudo().search([
        ('user_id', '=', user.id),
        ('company_id', 'in', user.company_ids.ids),
    ], limit=1)
    if employee:
        return employee
    # 2. Fallback: work_email == user.login (normalizar para comparación)
    login_normalized = (user.login or '').strip().lower()
    if not login_normalized:
        return env['hr.employee']
    employee = env['hr.employee'].sudo().search([
        ('work_email', 'ilike', login_normalized),
        ('company_id', 'in', user.company_ids.ids),
    ], limit=1)
    if employee:
        if not employee.user_id:
            employee.sudo().write({'user_id': user.id})
        return employee
    return env['hr.employee']
