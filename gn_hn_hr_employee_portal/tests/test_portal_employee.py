# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged
from odoo.addons.mail.tests.common import mail_new_test_user


@tagged('post_install', '-at_install', 'gn_hn_hr_employee_portal')
class TestPortalEmployee(HttpCase):
    """Tests mínimos del portal de empleados."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.emp_a = cls.env['hr.employee'].create({
            'name': 'Empleado A',
            'work_email': 'portal_a',  # Coincide con login para get_employee_from_user
        })
        cls.emp_b = cls.env['hr.employee'].create({
            'name': 'Empleado B',
            'work_email': 'portal_b',
        })
        cls.user_a = mail_new_test_user(
            cls.env,
            login='portal_a',
            name='Empleado A',
            groups='gn_hn_hr_employee_portal.group_employee_portal_user',
            email='emp_a@test.com',
        )
        cls.user_b = mail_new_test_user(
            cls.env,
            login='portal_b',
            name='Empleado B',
            groups='gn_hn_hr_employee_portal.group_employee_portal_user',
            email='emp_b@test.com',
        )
        # work_email = login para que get_employee_from_user encuentre al empleado

    def test_portal_employee_home_requires_login(self):
        """Portal /my/employee requiere autenticación."""
        response = self.url_open('/my/employee')
        self.assertIn('login', response.url.lower())

    def test_portal_employee_a_sees_home(self):
        """Usuario A autenticado puede acceder al portal."""
        self.authenticate('portal_a', 'portal_a')
        response = self.url_open('/my/employee')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Empleado A', response.content)

    def test_portal_employee_b_cannot_see_employee_a_profile_requests(self):
        """Usuario B no ve solicitudes de perfil de empleado A (record rule)."""
        profile_req = self.env['gn.hr.profile.change.request'].sudo().create({
            'employee_id': self.emp_a.id,
            'requested_by': self.user_a.id,
        })
        self.authenticate('portal_b', 'portal_b')
        # Por record rule, B solo ve sus propias solicitudes (employee_id.user_id = B)
        found = self.env['gn.hr.profile.change.request'].with_user(self.user_b).search([
            ('id', '=', profile_req.id)
        ])
        self.assertEqual(len(found), 0, 'Usuario B no debe ver solicitudes de A')

    def test_manager_sees_team_leaves(self):
        """Jefe con subalternos ve ausencias del equipo."""
        self.emp_b.parent_id = self.emp_a.id
        self.authenticate('portal_a', 'portal_a')
        response = self.url_open('/my/team/leaves')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Ausencias', response.content)

    def test_manager_team_leave_new_form_loads(self):
        """Formulario para solicitar ausencia por subalterno."""
        self.emp_b.parent_id = self.emp_a.id
        self.authenticate('portal_a', 'portal_a')
        response = self.url_open('/my/team/leaves/new')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Colaborador', response.content)

    def test_portal_salary_advances_list(self):
        """Listado de anticipos salariales accesible para el empleado portal."""
        self.authenticate('portal_a', 'portal_a')
        response = self.url_open('/my/salary-advances')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Anticipos', response.content)
