# -*- coding: utf-8 -*-
import base64
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare
from ..models.portal_employee_mixin import get_employee_from_user
from ..models.portal_upload_utils import validate_upload

ITEMS_PER_PAGE = 20


class EmployeePortal(CustomerPortal):
    _PORTAL_CARD_PARAM = {
        'profile': 'gn_hn_hr_employee_portal.portal_card_profile',
        'requests': 'gn_hn_hr_employee_portal.portal_card_requests',
        'certificates': 'gn_hn_hr_employee_portal.portal_card_certificates',
        'leaves': 'gn_hn_hr_employee_portal.portal_card_leaves',
        'personal_calendar': 'gn_hn_hr_employee_portal.portal_card_personal_calendar',
        'attendances': 'gn_hn_hr_employee_portal.portal_card_attendances',
        'payslips': 'gn_hn_hr_employee_portal.portal_card_payslips',
        'salary_advances': 'gn_hn_hr_employee_portal.portal_card_salary_advances',
        'team_leaves': 'gn_hn_hr_employee_portal.portal_card_team_leaves',
        'team_calendar': 'gn_hn_hr_employee_portal.enable_team_calendar',
    }

    def _portal_card_enabled(self, key):
        param = self._PORTAL_CARD_PARAM.get(key)
        if not param:
            return True
        raw = request.env['ir.config_parameter'].sudo().get_param(param)
        if raw is False or raw is None:
            return True
        return str(raw).lower() in ('1', 'true', 'yes')

    def _portal_guard_card_http(self, key):
        if not self._portal_card_enabled(key):
            return request.redirect('/my/employee')
        return None

    def _portal_cards_dict(self):
        return {k: self._portal_card_enabled(k) for k in self._PORTAL_CARD_PARAM}

    def _get_employee(self):
        """Obtiene el empleado asociado al usuario actual (portal o interno)."""
        user = request.env.user
        return get_employee_from_user(request.env, user)

    def _get_employee_or_render_unlinked(self):
        """Obtiene empleado o renderiza template de no vinculado."""
        employee = self._get_employee()
        if not employee:
            return request.render(
                "gn_hn_hr_employee_portal.portal_employee_not_linked",
                {'page_name': 'employee_not_linked'}
            )
        return employee

    def _get_leave_dashboard_data(self, employee):
        """Prepara datos del dashboard de vacaciones/ausencias para el empleado.
        Si no puede solicitar vacaciones HN en portal, se omiten los totales del tipo principal
        de vacaciones, pero el resto de ausencias sigue visible."""
        LeaveType = request.env['hr.leave.type'].sudo()
        Leave = request.env['hr.leave']
        if not LeaveType._name or not Leave._name:
            return None
        vac_portal = getattr(employee, 'hn_vacation_requests_allowed', True)
        try:
            company_ids = request.env.companies.ids
            allocation_data = LeaveType.with_context(
                employee_id=employee.id,
                default_employee_id=employee.id,
                allowed_company_ids=company_ids,
            ).get_allocation_data_request(fields.Date.today(), hidden_allocations=False)
        except Exception:
            return None
        if not allocation_data:
            # Sin asignaciones: mostrar solo últimas solicitudes
            recent_leaves = Leave.search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.gn_for_employee_portal', '=', True),
            ], order='date_from desc', limit=10)
            return {
                'totals': {'asignadas': 0, 'tomadas': 0, 'pendientes': 0, 'disponibles': 0, 'solicitables': 0},
                'by_type': [],
                'recent_leaves': recent_leaves,
            }
        totals = {'asignadas': 0, 'tomadas': 0, 'pendientes': 0, 'disponibles': 0, 'solicitables': 0}
        by_type = []
        for lt_name, data, _req, lt_id in allocation_data:
            lt = LeaveType.browse(lt_id)
            if not lt.gn_for_employee_portal:
                continue
            if getattr(lt, 'gn_vacation_is_primary', False) and not vac_portal:
                continue
            max_leaves = round(data.get('max_leaves', 0), 2)
            leaves_taken = round(data.get('leaves_taken', 0), 2)
            leaves_requested = round(data.get('leaves_requested', 0), 2)
            virtual_remaining = round(data.get('virtual_remaining_leaves', 0), 2)
            solicitables = virtual_remaining - leaves_requested if leaves_requested > 0 else virtual_remaining
            solicitables = max(0, round(solicitables, 2))
            totals['asignadas'] += max_leaves
            totals['tomadas'] += leaves_taken
            totals['pendientes'] += leaves_requested
            totals['disponibles'] += virtual_remaining
            totals['solicitables'] += solicitables
            by_type.append({
                'name': lt_name,
                'asignadas': max_leaves,
                'tomadas': leaves_taken,
                'pendientes': leaves_requested,
                'disponibles': virtual_remaining,
                'solicitables': solicitables,
                'sin_limite': data.get('allows_negative', False),
            })
        recent_leaves = Leave.search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id.gn_for_employee_portal', '=', True),
        ], order='date_from desc', limit=10)
        totals['asignadas'] = round(totals['asignadas'], 2)
        totals['tomadas'] = round(totals['tomadas'], 2)
        totals['pendientes'] = round(totals['pendientes'], 2)
        totals['disponibles'] = round(totals['disponibles'], 2)
        totals['solicitables'] = round(totals['solicitables'], 2)
        return {
            'totals': totals,
            'by_type': by_type,
            'recent_leaves': recent_leaves,
        }

    def _get_leave_balance_for_form(self, employee, leave_types):
        """Saldo para el formulario de solicitud: totales y límite por tipo."""
        LeaveType = request.env['hr.leave.type'].sudo()
        if not LeaveType._name or not leave_types:
            return None
        try:
            company_ids = request.env.companies.ids
            allocation_data = LeaveType.with_context(
                employee_id=employee.id,
                default_employee_id=employee.id,
                allowed_company_ids=company_ids,
            ).get_allocation_data_request(fields.Date.today(), hidden_allocations=False)
        except Exception:
            allocation_data = []
        vac_portal = getattr(employee, 'hn_vacation_requests_allowed', True)
        by_type_dict = {}
        for lt_name, data, _req, lt_id in allocation_data:
            lt = request.env['hr.leave.type'].sudo().browse(lt_id)
            if not lt.gn_for_employee_portal:
                continue
            if getattr(lt, 'gn_vacation_is_primary', False) and not vac_portal:
                continue
            virtual_remaining = round(data.get('virtual_remaining_leaves', 0), 2)
            leaves_requested = round(data.get('leaves_requested', 0), 2)
            solicitables = max(0, virtual_remaining - leaves_requested)
            by_type_dict[lt_id] = {
                'solicitables': solicitables,
                'sin_limite': data.get('allows_negative', False),
            }
        totals = {'disponibles': 0, 'solicitables': 0}
        for lt_name, data, _req, lt_id in allocation_data:
            lt = request.env['hr.leave.type'].sudo().browse(lt_id)
            if not lt.gn_for_employee_portal:
                continue
            if getattr(lt, 'gn_vacation_is_primary', False) and not vac_portal:
                continue
            totals['disponibles'] += round(data.get('virtual_remaining_leaves', 0), 2)
            totals['solicitables'] += max(0, round(data.get('virtual_remaining_leaves', 0), 2) -
                                         round(data.get('leaves_requested', 0), 2))
        totals['disponibles'] = round(totals['disponibles'], 2)
        totals['solicitables'] = round(totals['solicitables'], 2)
        type_limits = []
        for lt in leave_types:
            info = by_type_dict.get(lt.id)
            if info and info['sin_limite']:
                type_limits.append({'name': lt.name, 'limit': 'Sin límite'})
            elif info:
                type_limits.append({'name': lt.name, 'limit': '%.2f días' % info['solicitables']})
            else:
                type_limits.append({
                    'name': lt.name,
                    'limit': 'Sin límite' if getattr(lt, 'allows_negative', False) or not getattr(lt, 'requires_allocation', True) else '0.00 días'
                })
        return {
            'totals': totals,
            'type_limits': type_limits,
        }

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        employee = self._get_employee()
        if employee:
            values['employee'] = employee
            values['is_manager'] = bool(employee.child_ids)
        return values

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        employee = self._get_employee()
        if not employee:
            return values
        if 'profile_request_count' in counters:
            values['profile_request_count'] = request.env['gn.hr.profile.change.request'].search_count([
                ('employee_id', '=', employee.id)
            ])
        if 'certificate_request_count' in counters:
            values['certificate_request_count'] = request.env['gn.hr.work.certificate.request'].search_count([
                ('employee_id', '=', employee.id)
            ])
        if 'leave_count' in counters:
            values['leave_count'] = request.env['hr.leave'].search_count([
                ('employee_id', '=', employee.id)
            ])
        if 'attendance_count' in counters:
            values['attendance_count'] = request.env['hr.attendance'].search_count([
                ('employee_id', '=', employee.id)
            ])
        if 'payslip_count' in counters:
            values['payslip_count'] = request.env['hr.payslip'].search_count([
                ('employee_id', '=', employee.id)
            ])
        return values

    def _log_audit(self, action, model=None, res_id=None, employee_id=None):
        request.env['gn.hr.portal.audit.log'].sudo().log_action(
            action, model=model, res_id=res_id, employee_id=employee_id
        )

    @http.route(['/my', '/my/home'], type='http', auth="user", website=True)
    def home(self, **kw):
        """Redirige empleados portal a su dashboard o muestra portal estándar."""
        employee = self._get_employee()
        if employee:
            return request.redirect('/my/employee')
        return super().home(**kw)

    @http.route(['/my/employee', '/my/employee/page/<int:page>'], type='http', auth="user", website=True)
    def portal_employee_home(self, page=1, **kw):
        """Dashboard del portal de empleados."""
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        employee = result
        required = request.env['gn.hr.document.policy'].sudo().search([
            ('active', '=', True),
            ('required_for_portal', '=', True),
        ], order='sequence')
        accepted_ids = request.env['gn.hr.document.acceptance'].search([
            ('employee_id', '=', employee.id),
            ('policy_id', 'in', required.ids),
        ]).mapped('policy_id').ids
        pending = required.filtered(lambda p: p.id not in accepted_ids)
        if pending:
            return request.redirect('/my/policies?required=1')
        portal_cards = self._portal_cards_dict()
        values = {
            'employee': employee,
            'page_name': 'employee_portal',
            'is_manager': bool(employee.child_ids),
            'portal_cards': portal_cards,
        }
        # Dashboard de vacaciones (si hr_holidays y tarjeta Mis ausencias)
        if portal_cards.get('leaves'):
            leave_dashboard = self._get_leave_dashboard_data(employee)
            if leave_dashboard:
                values['leave_dashboard'] = leave_dashboard
        return request.render("gn_hn_hr_employee_portal.portal_employee_home", values)

    @http.route(['/my/policies'], type='http', auth="user", website=True)
    def portal_my_policies(self, **kw):
        """Lista de políticas pendientes de aceptar."""
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        employee = result
        policies = request.env['gn.hr.document.policy'].sudo().search([
            ('active', '=', True),
        ], order='sequence')
        accepted_ids = request.env['gn.hr.document.acceptance'].search([
            ('employee_id', '=', employee.id),
            ('policy_id', 'in', policies.ids),
        ]).mapped('policy_id').ids
        pending = policies.filtered(lambda p: p.id not in accepted_ids)
        return request.render("gn_hn_hr_employee_portal.portal_my_policies", {
            'employee': employee,
            'policies': policies,
            'pending_ids': pending.ids,
            'required': kw.get('required') == '1',
            'page_name': 'policies',
        })

    @http.route(['/my/policies/accept/<int:policy_id>'], type='http', auth="user", website=True, methods=['POST'])
    def portal_my_policy_accept(self, policy_id, **kw):
        """Registra aceptación de una política."""
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        employee = result
        policy = request.env['gn.hr.document.policy'].sudo().browse(policy_id)
        if not policy.exists() or not policy.active:
            return request.redirect('/my/policies')
        existing = request.env['gn.hr.document.acceptance'].search([
            ('employee_id', '=', employee.id),
            ('policy_id', '=', policy_id),
        ], limit=1)
        if not existing:
            ip = request.httprequest.environ.get('REMOTE_ADDR', '')
            user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')[:500]
            request.env['gn.hr.document.acceptance'].sudo().create({
                'employee_id': employee.id,
                'policy_id': policy_id,
                'ip': ip,
                'user_agent': user_agent,
            })
        return request.redirect('/my/policies')

    # --- Perfil ---
    @http.route(['/my/employee/profile'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_employee_profile(self, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('profile')
        if redir:
            return redir
        employee = result
        if request.httprequest.method == 'POST':
            vals = {
                'employee_id': employee.id,
                'phone_personal': kw.get('phone_personal'),
                'mobile_phone': kw.get('mobile_phone'),
                'address': kw.get('address'),
                'emergency_contact': kw.get('emergency_contact'),
                'emergency_contact_phone': kw.get('emergency_contact_phone'),
            }
            req = request.env['gn.hr.profile.change.request'].sudo().create(vals)
            self._log_audit('profile_change_request', model='gn.hr.profile.change.request', res_id=req.id, employee_id=employee.id)
            if self._portal_card_enabled('requests'):
                return request.redirect('/my/requests?success=1')
            return request.redirect('/my/employee')
        return request.render("gn_hn_hr_employee_portal.portal_employee_profile", {
            'employee': employee,
            'page_name': 'profile',
        })

    # --- Mis Solicitudes ---
    @http.route(['/my/requests', '/my/requests/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_requests(self, page=1, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('requests')
        if redir:
            return redir
        employee = result
        ProfileRequest = request.env['gn.hr.profile.change.request']
        CertRequest = request.env['gn.hr.work.certificate.request']
        Leave = request.env['hr.leave']
        profile_requests = ProfileRequest.search([('employee_id', '=', employee.id)], order='requested_on desc')
        cert_requests = CertRequest.search([('employee_id', '=', employee.id)], order='request_date desc')
        leaves = Leave.search([('employee_id', '=', employee.id)], order='date_from desc')
        Advance = request.env['salary.advance']
        sel_state = dict(Advance._fields['state'].selection)
        advances = Advance.search([('employee_id', '=', employee.id)], order='date desc, id desc')
        items = []
        if self._portal_card_enabled('profile'):
            for r in profile_requests:
                items.append({'type': 'profile', 'date': r.requested_on, 'state': r.state, 'state_label': r.state, 'obj': r, 'url': '/my/employee/profile'})
        if self._portal_card_enabled('certificates'):
            for r in cert_requests:
                items.append({'type': 'certificate', 'date': r.request_date, 'state': r.state, 'state_label': r.state, 'obj': r, 'url': '/my/certificates/%s' % r.id})
        if self._portal_card_enabled('leaves'):
            for r in leaves:
                items.append({'type': 'leave', 'date': r.date_from, 'state': r.state, 'state_label': r.state, 'obj': r, 'url': '/my/leaves'})
        if self._portal_card_enabled('salary_advances'):
            for r in advances:
                items.append({
                    'type': 'advance',
                    'date': r.date,
                    'state': r.state,
                    'state_label': sel_state.get(r.state, r.state),
                    'obj': r,
                    'url': '/my/salary-advances/%s' % r.id,
                })
        items.sort(key=lambda x: x['date'] or fields.Datetime.min, reverse=True)
        return request.render("gn_hn_hr_employee_portal.portal_my_requests", {
            'employee': employee,
            'items': items,
            'page_name': 'requests',
            'success': kw.get('success'),
        })

    # --- Anticipos salariales (flujo backend: salary.advance) ---
    @http.route(['/my/salary-advances', '/my/salary-advances/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_salary_advances(self, page=1, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('salary_advances')
        if redir:
            return redir
        employee = result
        Advance = request.env['salary.advance']
        domain = [('employee_id', '=', employee.id)]
        count = Advance.search_count(domain)
        pager = portal_pager(url="/my/salary-advances", total=count, page=page, step=ITEMS_PER_PAGE)
        advances = Advance.search(domain, limit=ITEMS_PER_PAGE, offset=pager['offset'], order='date desc, id desc')
        return request.render("gn_hn_hr_employee_portal.portal_my_salary_advances", {
            'employee': employee,
            'advances': advances,
            'pager': pager,
            'page_name': 'salary_advances',
            'success': kw.get('success'),
            'error': kw.get('error'),
        })

    @http.route(['/my/salary-advances/new'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_my_salary_advances_new(self, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('salary_advances')
        if redir:
            return redir
        employee = result
        Advance = request.env['salary.advance']
        selection = Advance._fields['advance_target'].selection
        limit_date = fields.Date.today()
        advance_limits_by_target = {
            key: Advance._advance_limit_values(employee, limit_date, key)
            for key, _ in selection
        }
        if request.httprequest.method == 'POST':
            target = kw.get('advance_target') or 'payroll'
            valid_targets = {k for k, _ in selection}
            if target not in valid_targets:
                target = 'payroll'
            try:
                amount = float(kw.get('advance_amount') or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
            advance_limit = Advance._advance_limit_values(employee, limit_date, target)
            advance_limits_by_target = {
                key: Advance._advance_limit_values(employee, limit_date, key)
                for key, _ in selection
            }
            max_amt = advance_limit['max_advance_amount']
            if max_amt > 0 and float_compare(amount, max_amt, precision_digits=2) > 0:
                return request.render("gn_hn_hr_employee_portal.portal_my_salary_advances_new", {
                    'employee': employee,
                    'advance_targets': selection,
                    'page_name': 'salary_advances_new',
                    'advance_limit': advance_limit,
                    'advance_limits_by_target': advance_limits_by_target,
                    'form_values': {
                        'advance_target': target,
                        'advance_amount': kw.get('advance_amount') or '',
                        'notes': kw.get('notes') or '',
                    },
                    'error': _(
                        'El monto solicitado (%.2f) supera el máximo permitido (%.2f).'
                    ) % (amount, max_amt),
                })
            vals = {
                'advance_target': target,
                'advance_amount': amount,
                'date': fields.Date.today(),
                'notes': kw.get('notes'),
            }
            try:
                advance = Advance.create(vals)
                advance.action_submit()
            except (UserError, ValidationError) as err:
                return request.render("gn_hn_hr_employee_portal.portal_my_salary_advances_new", {
                    'employee': employee,
                    'advance_targets': selection,
                    'page_name': 'salary_advances_new',
                    'advance_limit': advance_limit,
                    'advance_limits_by_target': advance_limits_by_target,
                    'form_values': {
                        'advance_target': target,
                        'advance_amount': kw.get('advance_amount') or '',
                        'notes': kw.get('notes') or '',
                    },
                    'error': err.args[0] if (err.args and isinstance(err.args[0], str)) else str(err),
                })
            self._log_audit('salary_advance_submit', model='salary.advance', res_id=advance.id, employee_id=employee.id)
            return request.redirect('/my/salary-advances?success=1')
        return request.render("gn_hn_hr_employee_portal.portal_my_salary_advances_new", {
            'employee': employee,
            'advance_targets': selection,
            'page_name': 'salary_advances_new',
            'form_values': {},
            'error': None,
            'advance_limit': advance_limits_by_target.get('payroll'),
            'advance_limits_by_target': advance_limits_by_target,
        })

    @http.route(['/my/salary-advances/<int:advance_id>'], type='http', auth='user', website=True)
    def portal_my_salary_advance_detail(self, advance_id, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('salary_advances')
        if redir:
            return redir
        employee = result
        advance = request.env['salary.advance'].browse(advance_id)
        if not advance.exists() or advance.employee_id.id != employee.id:
            return request.redirect('/my/salary-advances')
        sel_state = dict(advance._fields['state'].selection)
        sel_target = dict(advance._fields['advance_target'].selection)
        return request.render("gn_hn_hr_employee_portal.portal_my_salary_advance_detail", {
            'employee': employee,
            'advance': advance,
            'state_label': sel_state.get(advance.state, advance.state),
            'target_label': sel_target.get(advance.advance_target, advance.advance_target),
            'page_name': 'salary_advance_detail',
        })

    # --- Constancias ---
    @http.route(['/my/certificates', '/my/certificates/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_certificates(self, page=1, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('certificates')
        if redir:
            return redir
        employee = result
        domain = [('employee_id', '=', employee.id)]
        count = request.env['gn.hr.work.certificate.request'].search_count(domain)
        pager = portal_pager(url="/my/certificates", total=count, page=page, step=ITEMS_PER_PAGE)
        requests = request.env['gn.hr.work.certificate.request'].search(
            domain, limit=ITEMS_PER_PAGE, offset=pager['offset'], order='request_date desc'
        )
        return request.render("gn_hn_hr_employee_portal.portal_my_certificates", {
            'employee': employee,
            'requests': requests,
            'pager': pager,
            'page_name': 'certificates',
        })

    @http.route(['/my/certificates/new'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_my_certificates_new(self, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('certificates')
        if redir:
            return redir
        employee = result
        if request.httprequest.method == 'POST':
            recipient_id = kw.get('recipient_id')
            cert_type_id = int(kw.get('certificate_type_id', 0))
            vals = {
                'employee_id': employee.id,
                'certificate_type_id': cert_type_id,
                'recipient_id': int(recipient_id) if recipient_id else False,
                'notes': kw.get('notes'),
            }
            if cert_type_id:
                cert_type = request.env['hr.work.certificate.type'].sudo().browse(cert_type_id)
                if cert_type.exists() and cert_type.default_footer_id:
                    vals['footer_id'] = cert_type.default_footer_id.id
            if employee.current_version_id:
                vals['version_id'] = employee.current_version_id.id
            if employee.company_id:
                vals['company_id'] = employee.company_id.id
            req = request.env['gn.hr.work.certificate.request'].sudo().create(vals)
            self._log_audit('certificate_request', model='gn.hr.work.certificate.request', res_id=req.id, employee_id=employee.id)
            return request.redirect('/my/certificates')
        dom = [
            ('active', '=', True),
            ('for_portal', '=', True),
        ]
        if employee.company_id:
            dom.append(('company_id', '=', employee.company_id.id))
        types = request.env['hr.work.certificate.type'].sudo().search(dom, order='sequence, name')
        rec_dom = []
        if employee.company_id:
            rec_dom.append(('company_id', '=', employee.company_id.id))
        recipients = request.env['hr.certificate.recipient'].sudo().search(rec_dom, order='name')
        return request.render("gn_hn_hr_employee_portal.portal_my_certificates_new", {
            'employee': employee,
            'certificate_types': types,
            'recipients': recipients,
            'page_name': 'certificates_new',
        })

    @http.route(['/my/certificates/<int:request_id>'], type='http', auth="user", website=True)
    def portal_my_certificate_detail(self, request_id, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('certificates')
        if redir:
            return redir
        employee = result
        req = request.env['gn.hr.work.certificate.request'].sudo().browse(request_id)
        if not req.exists() or req.employee_id != employee:
            return request.redirect('/my/certificates')
        return request.render("gn_hn_hr_employee_portal.portal_my_certificate_detail", {
            'employee': employee,
            'cert_request': req,
            'page_name': 'certificate_detail',
        })

    @http.route(['/my/certificates/<int:request_id>/download'], type='http', auth="user", website=True)
    def portal_my_certificate_download(self, request_id, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('certificates')
        if redir:
            return redir
        employee = result
        req = request.env['gn.hr.work.certificate.request'].sudo().browse(request_id)
        if not req.exists() or req.employee_id != employee or req.state != 'issued' or not req.issued_document_id:
            raise AccessError(_('No puede descargar este documento.'))
        self._log_audit('certificate_download', model='gn.hr.work.certificate.request', res_id=req.id, employee_id=employee.id)
        content = base64.b64decode(req.issued_document_id.datas)
        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', 'attachment; filename="%s"' % (req.issued_document_id.name or 'constancia.pdf')),
            ]
        )

    # --- Ausencias ---
    @http.route(['/my/leaves', '/my/leaves/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_leaves(self, page=1, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('leaves')
        if redir:
            return redir
        employee = result
        domain = [('employee_id', '=', employee.id)]
        count = request.env['hr.leave'].search_count(domain)
        pager = portal_pager(url="/my/leaves", total=count, page=page, step=ITEMS_PER_PAGE)
        leaves = request.env['hr.leave'].search(domain, limit=ITEMS_PER_PAGE, offset=pager['offset'], order='date_from desc')
        return request.render("gn_hn_hr_employee_portal.portal_my_leaves", {
            'employee': employee,
            'leaves': leaves,
            'pager': pager,
            'page_name': 'leaves',
        })

    def _time_to_float(self, time_str):
        """Convierte 'HH:MM' o 'H' a float (ej: '08:30' -> 8.5, '8' -> 8.0). Solo horas enteras."""
        if not time_str:
            return 0.0
        try:
            parts = str(time_str).strip().split(':')
            h = int(parts[0]) if parts else 0
            # Ignorar minutos: solo horas enteras
            return float(h)
        except (ValueError, IndexError):
            return 0.0

    def _process_leave_attachments(self, files, leave):
        """Procesa archivos subidos, valida y crea ir.attachment. Retorna lista de ids."""
        env = request.env
        Attachment = env['ir.attachment'].sudo()
        ids = []
        file_list = files.getlist('attachment') if hasattr(files, 'getlist') else [
            files.get(k) for k in files if files.get(k) and getattr(files.get(k), 'filename', None)
        ]
        for f in file_list:
            if not f or not getattr(f, 'filename', None) or not (f.filename or '').strip():
                continue
            validate_upload(f, env, f.filename)
            f.seek(0)
            data = f.read()
            att = Attachment.create({
                'name': f.filename,
                'datas': base64.b64encode(data),
                'res_model': 'hr.leave',
                'res_id': leave.id,
            })
            ids.append(att.id)
        return ids

    def _get_calendar_hour_range(self, employee):
        """Devuelve lista de horas enteras del rango laboral del calendario del empleado."""
        calendar = employee.sudo().resource_calendar_id or (
            employee.company_id and employee.company_id.resource_calendar_id
        ) or request.env.company.resource_calendar_id
        if not calendar:
            return list(range(8, 18))  # fallback 8-17
        attendances = calendar.attendance_ids.filtered(
            lambda a: not a.display_type and a.day_period != 'lunch'
        )
        if not attendances:
            return list(range(8, 18))
        hour_min = int(min(attendances.mapped('hour_from')))
        hour_max = int(max(attendances.mapped('hour_to')))
        return list(range(hour_min, hour_max + 1))

    def _portal_leave_form_render_context(self, leave_owner, for_team_manager=False):
        """Datos comunes para el formulario de nueva ausencia (portal).

        ``hn_vacation_requests_allowed`` solo restringe al empleado que entra a *Mis ausencias*;
        si ``for_team_manager`` es True (solicitud por jefe), no se ocultan tipos de vacaciones principal.
        """
        company_ids = [leave_owner.company_id.id] if leave_owner.company_id else []
        company_ids.append(False)
        country_id = leave_owner.company_id.country_id.id if leave_owner.company_id and leave_owner.company_id.country_id else False
        domain = [
            ('company_id', 'in', company_ids),
            ('active', '=', True),
            ('gn_for_employee_portal', '=', True),
            '|', ('country_id', '=', False), ('country_id', '=', country_id),
            '|', ('requires_allocation', '=', False), ('has_valid_allocation', '=', True),
        ]
        leave_types = request.env['hr.leave.type'].with_context(
            default_employee_id=leave_owner.id,
            employee_id=leave_owner.id,
        ).sudo().search(domain, order='sequence')
        if not leave_types:
            leave_types = request.env['hr.leave.type'].sudo().search([
                ('company_id', 'in', company_ids),
                ('active', '=', True),
                ('gn_for_employee_portal', '=', True),
                '|', ('country_id', '=', False), ('country_id', '=', country_id),
            ], order='sequence')
        if not for_team_manager and not getattr(leave_owner, 'hn_vacation_requests_allowed', True):
            leave_types = leave_types.filtered(lambda lt: not getattr(lt, 'gn_vacation_is_primary', False))
        calendar_hours = self._get_calendar_hour_range(leave_owner)
        enable_leave_attachments = request.env['ir.config_parameter'].sudo().get_param(
            'gn_hn_hr_employee_portal.enable_portal_leave_attachments'
        ) == 'True'
        leave_balance = self._get_leave_balance_for_form(leave_owner, leave_types)
        user_tz = (leave_owner.tz or request.env.user.tz or request.env.company.tz or 'UTC')
        return {
            'leave_types': leave_types,
            'calendar_hours': calendar_hours,
            'enable_leave_attachments': enable_leave_attachments,
            'leave_balance': leave_balance,
            'user_tz': user_tz,
        }

    def _portal_create_leave_from_post(self, kw, leave_owner, portal_user, gn_portal_submitter=False, for_team_manager=False):
        holiday_status_id = int(kw.get('holiday_status_id', 0))
        leave_type = request.env['hr.leave.type'].sudo().browse(holiday_status_id)
        if leave_type.exists() and not leave_type.gn_for_employee_portal:
            raise UserError(_('Este tipo de ausencia no está disponible en el portal.'))
        if (
            not for_team_manager
            and leave_type.exists()
            and getattr(leave_type, 'gn_vacation_is_primary', False)
            and not getattr(leave_owner, 'hn_vacation_requests_allowed', True)
        ):
            raise UserError(
                _('No tiene permitido solicitar vacaciones (tipo principal) desde el portal. Contacte a Recursos Humanos.')
            )
        date_from = kw.get('request_date_from') or kw.get('date_from')
        date_to = kw.get('request_date_to') or kw.get('date_to')
        if date_from and leave_type.exists():
            try:
                req_start = fields.Date.from_string(date_from)
            except (ValueError, TypeError):
                req_start = None
            if req_start:
                ann_check = getattr(
                    request.env['hr.leave'], '_gn_assert_anniversary_vacation_start', None
                )
                if ann_check:
                    try:
                        ann_check(leave_owner, leave_type, req_start)
                    except ValidationError as err:
                        raise UserError(err.args[0]) from err
        vals = {
            'employee_id': leave_owner.id,
            'holiday_status_id': holiday_status_id,
            'request_date_from': date_from,
            'request_date_to': date_to or date_from,
            'notes': kw.get('notes', ''),
        }
        if gn_portal_submitter:
            vals['gn_portal_submitter_id'] = portal_user.id
        if leave_type.exists():
            if leave_type.request_unit == 'half_day':
                vals['request_date_from_period'] = kw.get('request_date_from_period', 'am')
                vals['request_date_to_period'] = kw.get('request_date_to_period', 'pm')
            elif leave_type.request_unit == 'hour':
                vals['request_hour_from'] = self._time_to_float(kw.get('request_hour_from'))
                vals['request_hour_to'] = self._time_to_float(kw.get('request_hour_to'))
        leave = request.env['hr.leave'].sudo().with_context(
            gn_leave_real_uid=portal_user.id,
        ).create(vals)
        return leave, leave_type

    @http.route(['/my/leaves/new'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_my_leaves_new(self, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('leaves')
        if redir:
            return redir
        employee = result
        if request.httprequest.method == 'POST':
            leave, _leave_type = self._portal_create_leave_from_post(
                kw, employee, request.env.user, gn_portal_submitter=False,
            )
            if request.env['ir.config_parameter'].sudo().get_param(
                'gn_hn_hr_employee_portal.enable_portal_leave_attachments'
            ) == 'True':
                attachment_ids = self._process_leave_attachments(request.httprequest.files, leave)
                if attachment_ids:
                    leave.sudo().write({'attachment_ids': [(6, 0, attachment_ids)]})
            return request.redirect('/my/leaves')
        ctx = self._portal_leave_form_render_context(employee)
        ctx.update({
            'employee': employee,
            'page_name': 'leaves_new',
        })
        return request.render("gn_hn_hr_employee_portal.portal_my_leaves_new", ctx)

    @http.route(['/my/leaves/simulate'], type='jsonrpc', auth="user")
    def portal_my_leaves_simulate(self, holiday_status_id, request_date_from, request_date_to=None, **kw):
        """Simula días/horas de una solicitud y devuelve saldo disponible."""
        if not self._portal_card_enabled('leaves'):
            return {'error': str(_('Esta sección no está disponible en el portal.'))}
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return {'error': 'no_employee'}
        employee = result
        request_date_to = request_date_to or request_date_from
        leave_type = request.env['hr.leave.type'].sudo().browse(int(holiday_status_id))
        if not leave_type.exists():
            return {'error': 'invalid_type'}
        if not leave_type.gn_for_employee_portal:
            return {'error': str(_('Este tipo de ausencia no está disponible en el portal.'))}
        if getattr(leave_type, 'gn_vacation_is_primary', False) and not getattr(employee, 'hn_vacation_requests_allowed', True):
            return {'error': str(_('No tiene permitido solicitar vacaciones Honduras desde el portal. Contacte a Recursos Humanos.'))}
        try:
            req_start = fields.Date.from_string(request_date_from)
        except (ValueError, TypeError):
            req_start = None
        if req_start:
            ann_check = getattr(request.env['hr.leave'], '_gn_assert_anniversary_vacation_start', None)
            if ann_check:
                try:
                    ann_check(employee, leave_type, req_start)
                except ValidationError as err:
                    return {'error': str(err.args[0])}
        try:
            vals = {
                'employee_id': employee.id,
                'holiday_status_id': leave_type.id,
                'request_date_from': request_date_from,
                'request_date_to': request_date_to,
            }
            if leave_type.request_unit == 'half_day':
                vals['request_date_from_period'] = kw.get('request_date_from_period', 'am')
                vals['request_date_to_period'] = kw.get('request_date_to_period', 'pm')
            elif leave_type.request_unit == 'hour':
                vals['request_hour_from'] = self._time_to_float(kw.get('request_hour_from'))
                vals['request_hour_to'] = self._time_to_float(kw.get('request_hour_to'))
            fake = request.env['hr.leave'].sudo().with_context(
                default_employee_id=employee.id,
                employee_id=employee.id,
                default_request_date_from=request_date_from,
            ).new(vals)
            fake._compute_duration()
            fake._compute_leaves()
            return {
                'number_of_days': round(fake.number_of_days, 2),
                'number_of_hours': round(fake.number_of_hours, 2),
                'virtual_remaining_leaves': round(fake.virtual_remaining_leaves, 2),
            }
        except Exception as e:
            return {'error': str(e)}

    @http.route(['/my/team/leaves/new'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_team_leaves_new(self, **kw):
        """Solicitud de ausencia en nombre de un subalterno directo (jefe portal)."""
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('team_leaves')
        if redir:
            return redir
        manager = result
        if not manager.child_ids:
            return request.redirect('/my/employee')
        subordinates = manager.child_ids
        if request.httprequest.method == 'POST':
            try:
                target_id = int(kw.get('target_employee_id', 0))
            except (ValueError, TypeError):
                target_id = 0
            target = subordinates.filtered(lambda e: e.id == target_id)
            if not target:
                raise UserError(_('Seleccione un colaborador válido de su equipo.'))
            target = target[0]
            leave, _lt = self._portal_create_leave_from_post(
                kw, target, request.env.user, gn_portal_submitter=True, for_team_manager=True,
            )
            if request.env['ir.config_parameter'].sudo().get_param(
                'gn_hn_hr_employee_portal.enable_portal_leave_attachments'
            ) == 'True':
                attachment_ids = self._process_leave_attachments(request.httprequest.files, leave)
                if attachment_ids:
                    leave.sudo().write({'attachment_ids': [(6, 0, attachment_ids)]})
            return request.redirect('/my/team/leaves')
        try:
            sel_id = int(kw.get('employee_id', 0))
        except (ValueError, TypeError):
            sel_id = 0
        selected = subordinates.filtered(lambda e: e.id == sel_id)
        target_employee = selected[0] if selected else subordinates[0]
        ctx = self._portal_leave_form_render_context(target_employee, for_team_manager=True)
        ctx.update({
            'employee': target_employee,
            'manager_employee': manager,
            'subordinates': subordinates,
            'page_name': 'team_leaves_new',
        })
        return request.render('gn_hn_hr_employee_portal.portal_team_leaves_new', ctx)

    @http.route(['/my/team/leaves/simulate'], type='jsonrpc', auth='user')
    def portal_team_leaves_simulate(self, employee_id, holiday_status_id, request_date_from, request_date_to=None, **kw):
        if not self._portal_card_enabled('team_leaves'):
            return {'error': str(_('Esta sección no está disponible en el portal.'))}
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return {'error': 'no_employee'}
        manager = result
        if not manager.child_ids:
            return {'error': str(_('No tiene subalternos en el organigrama.'))}
        try:
            eid = int(employee_id)
        except (ValueError, TypeError):
            return {'error': 'invalid_employee'}
        employee = manager.child_ids.filtered(lambda e: e.id == eid)
        if not employee:
            return {'error': str(_('Empleado no pertenece a su equipo.'))}
        employee = employee[0]
        request_date_to = request_date_to or request_date_from
        leave_type = request.env['hr.leave.type'].sudo().browse(int(holiday_status_id))
        if not leave_type.exists():
            return {'error': 'invalid_type'}
        if not leave_type.gn_for_employee_portal:
            return {'error': str(_('Este tipo de ausencia no está disponible en el portal.'))}
        try:
            req_start = fields.Date.from_string(request_date_from)
        except (ValueError, TypeError):
            req_start = None
        if req_start:
            ann_check = getattr(request.env['hr.leave'], '_gn_assert_anniversary_vacation_start', None)
            if ann_check:
                try:
                    ann_check(employee, leave_type, req_start)
                except ValidationError as err:
                    return {'error': str(err.args[0])}
        try:
            vals = {
                'employee_id': employee.id,
                'holiday_status_id': leave_type.id,
                'request_date_from': request_date_from,
                'request_date_to': request_date_to,
            }
            if leave_type.request_unit == 'half_day':
                vals['request_date_from_period'] = kw.get('request_date_from_period', 'am')
                vals['request_date_to_period'] = kw.get('request_date_to_period', 'pm')
            elif leave_type.request_unit == 'hour':
                vals['request_hour_from'] = self._time_to_float(kw.get('request_hour_from'))
                vals['request_hour_to'] = self._time_to_float(kw.get('request_hour_to'))
            fake = request.env['hr.leave'].sudo().with_context(
                default_employee_id=employee.id,
                employee_id=employee.id,
                default_request_date_from=request_date_from,
            ).new(vals)
            fake._compute_duration()
            fake._compute_leaves()
            return {
                'number_of_days': round(fake.number_of_days, 2),
                'number_of_hours': round(fake.number_of_hours, 2),
                'virtual_remaining_leaves': round(fake.virtual_remaining_leaves, 2),
            }
        except Exception as e:
            return {'error': str(e)}

    def _portal_leave_check_kw_for_json(self, leave_type, kw):
        check_kw = dict(kw)
        if leave_type.request_unit == 'hour':
            check_kw['request_hour_from'] = self._time_to_float(kw.get('request_hour_from'))
            check_kw['request_hour_to'] = self._time_to_float(kw.get('request_hour_to'))
        return check_kw

    @http.route(['/my/leaves/check_restrictions'], type='jsonrpc', auth='user')
    def portal_my_leaves_check_restrictions(self, holiday_status_id, request_date_from, request_date_to=None, **kw):
        """JSON: solapamientos y restricciones antes de enviar (empleado portal)."""
        if not self._portal_card_enabled('leaves'):
            return {'error': str(_('Esta sección no está disponible en el portal.'))}
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return {'error': 'no_employee'}
        employee = result
        request_date_to = request_date_to or request_date_from
        leave_type = request.env['hr.leave.type'].sudo().browse(int(holiday_status_id))
        if not leave_type.exists():
            return {'error': 'invalid_type'}
        if not leave_type.gn_for_employee_portal:
            return {'error': str(_('Este tipo de ausencia no está disponible en el portal.'))}
        if (
            getattr(leave_type, 'gn_vacation_is_primary', False)
            and not getattr(employee, 'hn_vacation_requests_allowed', True)
        ):
            return {
                'blocking': [
                    str(_(
                        'No tiene permitido solicitar vacaciones Honduras desde el portal. '
                        'Contacte a Recursos Humanos.'
                    )),
                ],
                'warnings': [],
            }
        portal_user = request.env.user
        check_kw = self._portal_leave_check_kw_for_json(leave_type, kw)
        preview_lang = request.env.context.get('lang') or portal_user.lang or 'es_GT'
        return request.env['hr.leave'].sudo().with_context(
            gn_leave_real_uid=portal_user.id,
            lang=preview_lang,
        ).gn_portal_preview_leave_restrictions(
            employee,
            leave_type,
            request_date_from,
            request_date_to,
            **check_kw,
        )

    @http.route(['/my/team/leaves/check_restrictions'], type='jsonrpc', auth='user')
    def portal_team_leaves_check_restrictions(self, employee_id, holiday_status_id, request_date_from, request_date_to=None, **kw):
        """JSON: restricciones al solicitar ausencia por colaborador (jefe portal)."""
        if not self._portal_card_enabled('team_leaves'):
            return {'error': str(_('Esta sección no está disponible en el portal.'))}
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return {'error': 'no_employee'}
        manager = result
        if not manager.child_ids:
            return {'error': str(_('No tiene subalternos en el organigrama.'))}
        try:
            eid = int(employee_id)
        except (ValueError, TypeError):
            return {'error': 'invalid_employee'}
        employee = manager.child_ids.filtered(lambda e: e.id == eid)
        if not employee:
            return {'error': str(_('Empleado no pertenece a su equipo.'))}
        employee = employee[0]
        request_date_to = request_date_to or request_date_from
        leave_type = request.env['hr.leave.type'].sudo().browse(int(holiday_status_id))
        if not leave_type.exists():
            return {'error': 'invalid_type'}
        if not leave_type.gn_for_employee_portal:
            return {'error': str(_('Este tipo de ausencia no está disponible en el portal.'))}
        portal_user = request.env.user
        check_kw = self._portal_leave_check_kw_for_json(leave_type, kw)
        preview_lang = request.env.context.get('lang') or portal_user.lang or 'es_GT'
        return request.env['hr.leave'].sudo().with_context(
            gn_leave_real_uid=portal_user.id,
            lang=preview_lang,
        ).gn_portal_preview_leave_restrictions(
            employee,
            leave_type,
            request_date_from,
            request_date_to,
            **check_kw,
        )

    # --- Asistencias ---
    @http.route(['/my/attendances', '/my/attendances/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_attendances(self, page=1, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('attendances')
        if redir:
            return redir
        employee = result
        domain = [('employee_id', '=', employee.id)]
        count = request.env['hr.attendance'].search_count(domain)
        pager = portal_pager(url="/my/attendances", total=count, page=page, step=ITEMS_PER_PAGE)
        attendances = request.env['hr.attendance'].search(domain, limit=ITEMS_PER_PAGE, offset=pager['offset'], order='check_in desc')
        enable_punch = request.env['ir.config_parameter'].sudo().get_param('gn_hn_hr_employee_portal.enable_portal_attendance_punch') == 'True'
        last = request.env['hr.attendance'].search([('employee_id', '=', employee.id)], limit=1, order='check_in desc')
        checked_in = last and not last.check_out
        return request.render("gn_hn_hr_employee_portal.portal_my_attendances", {
            'employee': employee,
            'attendances': attendances,
            'pager': pager,
            'page_name': 'attendances',
            'enable_punch': enable_punch,
            'checked_in': checked_in,
        })

    @http.route(['/my/attendances/corrections', '/my/attendances/corrections/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_attendance_corrections(self, page=1, **kw):
        """Lista de solicitudes de corrección de asistencia."""
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('attendances')
        if redir:
            return redir
        employee = result
        domain = [('employee_id', '=', employee.id)]
        count = request.env['gn.hr.attendance.correction.request'].search_count(domain)
        pager = portal_pager(url="/my/attendances/corrections", total=count, page=page, step=ITEMS_PER_PAGE)
        corrections = request.env['gn.hr.attendance.correction.request'].search(
            domain, limit=ITEMS_PER_PAGE, offset=pager['offset'], order='request_date desc'
        )
        return request.render("gn_hn_hr_employee_portal.portal_my_attendance_corrections", {
            'employee': employee,
            'corrections': corrections,
            'pager': pager,
            'page_name': 'attendance_corrections',
        })

    @http.route(['/my/attendances/corrections/new'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_my_attendance_correction_new(self, **kw):
        """Nueva solicitud de corrección de asistencia."""
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('attendances')
        if redir:
            return redir
        employee = result
        if request.httprequest.method == 'POST':
            attendance_id = int(kw.get('attendance_id', 0))
            att = request.env['hr.attendance'].sudo().browse(attendance_id)
            if not att.exists() or att.employee_id != employee:
                return request.redirect('/my/attendances/corrections')
            requested_check_in = kw.get('requested_check_in', '').replace('T', ' ')
            if requested_check_in and len(requested_check_in) == 16:
                requested_check_in += ':00'
            requested_check_out = (kw.get('requested_check_out') or '').replace('T', ' ')
            if requested_check_out and len(requested_check_out) == 16:
                requested_check_out += ':00'
            requested_check_out = requested_check_out or False
            reason = kw.get('reason', '')
            if not requested_check_in or not reason:
                return request.redirect('/my/attendances/corrections/new?error=1')
            request.env['gn.hr.attendance.correction.request'].sudo().create({
                'employee_id': employee.id,
                'attendance_id': attendance_id,
                'requested_check_in': requested_check_in,
                'requested_check_out': requested_check_out or False,
                'reason': reason,
            })
            self._log_audit('attendance_correction_request', model='gn.hr.attendance.correction.request', employee_id=employee.id)
            return request.redirect('/my/attendances/corrections')
        attendances = request.env['hr.attendance'].search(
            [('employee_id', '=', employee.id)],
            order='check_in desc',
            limit=100,
        )
        return request.render("gn_hn_hr_employee_portal.portal_my_attendance_correction_new", {
            'employee': employee,
            'attendances': attendances,
            'page_name': 'attendance_correction_new',
            'error': kw.get('error'),
        })

    @http.route(['/my/attendances/punch'], type='http', auth="user", website=True, methods=['POST'])
    def portal_my_attendances_punch(self, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('attendances')
        if redir:
            return redir
        employee = result
        if request.env['ir.config_parameter'].sudo().get_param('gn_hn_hr_employee_portal.enable_portal_attendance_punch') != 'True':
            return request.redirect('/my/attendances')
        last = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1, order='check_in desc')
        if last:
            last.write({'check_out': fields.Datetime.now()})
        else:
            request.env['hr.attendance'].sudo().create({
                'employee_id': employee.id,
                'check_in': fields.Datetime.now(),
            })
        self._log_audit('attendance_punch', employee_id=employee.id)
        return request.redirect('/my/attendances')

    # --- Payslips ---
    @http.route(['/my/payslips', '/my/payslips/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_payslips(self, page=1, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('payslips')
        if redir:
            return redir
        employee = result
        domain = [('employee_id', '=', employee.id)]
        count = request.env['hr.payslip'].search_count(domain)
        pager = portal_pager(url="/my/payslips", total=count, page=page, step=ITEMS_PER_PAGE)
        payslips = request.env['hr.payslip'].search(domain, limit=ITEMS_PER_PAGE, offset=pager['offset'], order='date_from desc')
        return request.render("gn_hn_hr_employee_portal.portal_my_payslips", {
            'employee': employee,
            'payslips': payslips,
            'pager': pager,
            'page_name': 'payslips',
        })

    @http.route(['/my/payslips/<int:payslip_id>'], type='http', auth="user", website=True)
    def portal_my_payslip_detail(self, payslip_id, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('payslips')
        if redir:
            return redir
        employee = result
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists() or payslip.employee_id != employee:
            return request.redirect('/my/payslips')
        return request.render("gn_hn_hr_employee_portal.portal_my_payslip_detail", {
            'employee': employee,
            'payslip': payslip,
            'page_name': 'payslip_detail',
        })

    @http.route(['/my/payslips/<int:payslip_id>/download'], type='http', auth="user", website=True)
    def portal_my_payslip_download(self, payslip_id, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('payslips')
        if redir:
            return redir
        employee = result
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists() or payslip.employee_id != employee:
            raise AccessError(_('No puede descargar esta nómina.'))
        self._log_audit('payslip_download', model='hr.payslip', res_id=payslip.id, employee_id=employee.id)
        report = request.env.ref('hr_payroll.action_report_payslip', raise_if_not_found=False)
        if report:
            pdf, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(report.id, payslip.ids)
            return request.make_response(
                pdf,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', 'attachment; filename="payslip_%s.pdf"' % payslip.name),
                ]
            )
        return request.redirect('/my/payslips/%s' % payslip_id)

    # --- Vista de jefes: vacaciones del equipo ---
    @http.route(['/my/team/leaves', '/my/team/leaves/page/<int:page>'], type='http', auth="user", website=True)
    def portal_team_leaves(self, page=1, **kw):
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('team_leaves')
        if redir:
            return redir
        employee = result
        if not employee.child_ids:
            return request.redirect('/my/employee')
        subaltern_ids = employee.child_ids.ids
        domain = [('employee_id', 'in', subaltern_ids)]
        filter_emp = kw.get('filter_employee_id')
        if filter_emp:
            try:
                emp_id = int(filter_emp)
                if emp_id in subaltern_ids:
                    domain.append(('employee_id', '=', emp_id))
            except (ValueError, TypeError):
                pass
        filter_type = kw.get('filter_holiday_status_id')
        if filter_type:
            try:
                domain.append(('holiday_status_id', '=', int(filter_type)))
            except (ValueError, TypeError):
                pass
        filter_state = kw.get('filter_state')
        if filter_state:
            domain.append(('state', '=', filter_state))
        filter_date_from = kw.get('filter_date_from')
        if filter_date_from:
            domain.append(('request_date_from', '>=', filter_date_from))
        filter_date_to = kw.get('filter_date_to')
        if filter_date_to:
            domain.append(('request_date_to', '<=', filter_date_to))
        count = request.env['hr.leave'].sudo().search_count(domain)
        base_url = '/my/team/leaves'
        url_args = {k: v for k, v in kw.items() if v and k.startswith('filter_')}
        pager = portal_pager(
            url=base_url,
            total=count,
            page=page,
            step=ITEMS_PER_PAGE,
            url_args=url_args or None,
        )
        leaves = request.env['hr.leave'].sudo().search(
            domain,
            limit=ITEMS_PER_PAGE,
            offset=pager['offset'],
            order='date_from desc',
        )
        leave_types = request.env['hr.leave.type'].sudo().search([
            ('active', '=', True),
            ('company_id', 'in', [False, employee.company_id.id] if employee.company_id else [False]),
        ], order='name')
        return request.render("gn_hn_hr_employee_portal.portal_team_leaves", {
            'employee': employee,
            'leaves': leaves,
            'pager': pager,
            'subordinates': employee.child_ids,
            'leave_types': leave_types,
            'filter_employee_id': filter_emp,
            'filter_holiday_status_id': filter_type,
            'filter_state': filter_state,
            'filter_date_from': filter_date_from,
            'filter_date_to': filter_date_to,
            'page_name': 'team_leaves',
        })

    # --- Calendario ---
    @http.route(['/my/calendar'], type='http', auth="user", website=True)
    def portal_my_calendar(self, year=None, month=None, **kw):
        """Calendario personal de ausencias."""
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('personal_calendar')
        if redir:
            return redir
        employee = result
        return request.render("gn_hn_hr_employee_portal.portal_my_calendar", {
            'employee': employee,
            'page_name': 'calendar',
            'year': year,
            'month': month,
        })

    @http.route(['/my/calendar/events'], type='jsonrpc', auth="user")
    def portal_my_calendar_events(self, start, end, **kw):
        """Eventos del calendario personal (ausencias)."""
        if not self._portal_card_enabled('personal_calendar'):
            return []
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return []
        employee = result
        domain = [
            ('employee_id', '=', employee.id),
            ('date_from', '<', end),
            ('date_to', '>', start),
            ('state', '!=', 'cancel'),
            ('holiday_status_id.gn_for_employee_portal', '=', True),
        ]
        leaves = request.env['hr.leave'].search(domain)
        events = []
        for leave in leaves:
            events.append({
                'id': leave.id,
                'title': '%s - %s' % (leave.holiday_status_id.name, leave.employee_id.name),
                'start': leave.date_from.isoformat() if leave.date_from else '',
                'end': leave.date_to.isoformat() if leave.date_to else '',
                'url': '/my/leaves',
                'color': '#' + (leave.holiday_status_id.color and '%06x' % leave.holiday_status_id.color or '3498db'),
            })
        return events

    @http.route(['/my/team/calendar'], type='http', auth="user", website=True)
    def portal_team_calendar(self, year=None, month=None, **kw):
        """Calendario del equipo (ausencias de subalternos)."""
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return result
        redir = self._portal_guard_card_http('team_calendar')
        if redir:
            return redir
        employee = result
        if not employee.child_ids:
            return request.redirect('/my/employee')
        return request.render("gn_hn_hr_employee_portal.portal_team_calendar", {
            'employee': employee,
            'page_name': 'team_calendar',
            'year': year,
            'month': month,
        })

    @http.route(['/my/team/calendar/events'], type='jsonrpc', auth="user")
    def portal_team_calendar_events(self, start, end, **kw):
        """Eventos del calendario del equipo."""
        if not self._portal_card_enabled('team_calendar'):
            return []
        result = self._get_employee_or_render_unlinked()
        if not hasattr(result, 'id'):
            return []
        employee = result
        if not employee.child_ids:
            return []
        subaltern_ids = employee.child_ids.ids
        domain = [
            ('employee_id', 'in', subaltern_ids),
            ('date_from', '<', end),
            ('date_to', '>', start),
            ('state', '!=', 'cancel'),
        ]
        leaves = request.env['hr.leave'].sudo().search(domain)
        events = []
        for leave in leaves:
            events.append({
                'id': leave.id,
                'title': '%s - %s' % (leave.holiday_status_id.name, leave.employee_id.name),
                'start': leave.date_from.isoformat() if leave.date_from else '',
                'end': leave.date_to.isoformat() if leave.date_to else '',
                'url': '/my/team/leaves',
                'color': '#' + (leave.holiday_status_id.color and '%06x' % leave.holiday_status_id.color or '3498db'),
            })
        return events
