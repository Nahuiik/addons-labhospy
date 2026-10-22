# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models, tools


class GnHnVacationLibro(models.Model):
    _name = 'gn.hn.vacation.libro'
    _description = 'Libro de Vacaciones Honduras'
    _auto = False
    _order = 'employee_name, period_start desc'

    employee_id = fields.Many2one('hr.employee', string='Empleado', readonly=True)
    employee_name = fields.Char('Nombre empleado', readonly=True)
    department_id = fields.Many2one('hr.department', string='Departamento', readonly=True)
    job_id = fields.Many2one('hr.job', string='Puesto', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    period_start = fields.Date('Inicio período', readonly=True)
    period_end = fields.Date('Fin período', readonly=True)
    days_entitled = fields.Float('Días asignados', readonly=True, aggregator='sum')
    days_taken = fields.Float('Días gozados', readonly=True, aggregator='sum')
    days_remaining = fields.Float('Saldo', readonly=True, aggregator='sum')
    constancia_count = fields.Integer('Constancias', readonly=True, aggregator='sum')
    paid_count = fields.Integer('Pagos', readonly=True, aggregator='sum')
    seniority_years = fields.Integer('Antigüedad (años)', readonly=True)
    allocation_state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirm', 'Por aprobar'),
        ('validate', 'Aprobada'),
        ('refuse', 'Rechazada'),
    ], string='Estado asignación', readonly=True)
    contract_date_start = fields.Date('Fecha ingreso', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'gn_hn_vacation_libro')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW gn_hn_vacation_libro AS (
                SELECT
                    alloc.id AS id,
                    alloc.employee_id AS employee_id,
                    emp.name AS employee_name,
                    v.department_id AS department_id,
                    v.job_id AS job_id,
                    alloc.employee_company_id AS company_id,
                    alloc.hn_vacation_period_start AS period_start,
                    alloc.hn_vacation_period_end AS period_end,
                    alloc.number_of_days AS days_entitled,
                    COALESCE(taken.total_taken, 0) AS days_taken,
                    (alloc.number_of_days - COALESCE(taken.total_taken, 0)) AS days_remaining,
                    COALESCE(ccount.cnt, 0)::int AS constancia_count,
                    COALESCE(pcount.cnt, 0)::int AS paid_count,
                    COALESCE(EXTRACT(YEAR FROM AGE(CURRENT_DATE, v.contract_date_start)), 0)::int AS seniority_years,
                    alloc.state AS allocation_state,
                    v.contract_date_start AS contract_date_start
                FROM hr_leave_allocation alloc
                JOIN hr_employee emp ON emp.id = alloc.employee_id
                LEFT JOIN hr_version v ON v.id = emp.current_version_id
                JOIN hr_leave_type lt ON lt.id = alloc.holiday_status_id
                LEFT JOIN LATERAL (
                    SELECT COALESCE(SUM(lv.number_of_days), 0) AS total_taken
                    FROM hr_leave lv
                    WHERE lv.employee_id = alloc.employee_id
                      AND lv.holiday_status_id = alloc.holiday_status_id
                      AND lv.state IN ('validate', 'validate1')
                      AND (alloc.hn_vacation_period_start IS NULL
                           OR lv.request_date_from >= alloc.hn_vacation_period_start)
                      AND (alloc.hn_vacation_period_end IS NULL
                           OR lv.request_date_from <= alloc.hn_vacation_period_end)
                ) taken ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS cnt
                    FROM hr_leave lv
                    WHERE lv.employee_id = alloc.employee_id
                      AND lv.holiday_status_id = alloc.holiday_status_id
                      AND lv.state = 'validate'
                      AND lv.hn_constancia_signed = True
                      AND (alloc.hn_vacation_period_start IS NULL
                           OR lv.request_date_from >= alloc.hn_vacation_period_start)
                      AND (alloc.hn_vacation_period_end IS NULL
                           OR lv.request_date_from <= alloc.hn_vacation_period_end)
                ) ccount ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS cnt
                    FROM hr_leave lv
                    WHERE lv.employee_id = alloc.employee_id
                      AND lv.holiday_status_id = alloc.holiday_status_id
                      AND lv.state = 'validate'
                      AND lv.hn_paid_in_advance = True
                      AND (alloc.hn_vacation_period_start IS NULL
                           OR lv.request_date_from >= alloc.hn_vacation_period_start)
                      AND (alloc.hn_vacation_period_end IS NULL
                           OR lv.request_date_from <= alloc.hn_vacation_period_end)
                ) pcount ON TRUE
                WHERE lt.gn_vacation_is_primary = True
                  AND emp.active = True
            )
        """)
