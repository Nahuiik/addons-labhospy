# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class InvoicePaymentSavedView(models.Model):
    _name = 'gn.accounting.invoice.payment.saved.view'
    _description = 'Vista guardada — Facturas y pagos'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    is_default = fields.Boolean(string='Predeterminada')
    is_system = fields.Boolean(
        string='Vista rápida del sistema',
        default=False,
        help='Vistas predefinidas; no se pueden eliminar.',
    )
    sequence = fields.Integer(default=10)
    filter_json = fields.Text(string='Filtros (JSON)', required=True)

    _sql_constraints = [
        (
            'name_user_company_uniq',
            'unique(name, user_id, company_id)',
            'Ya existe una vista guardada con ese nombre.',
        ),
    ]

    @api.model
    def _check_report_access(self):
        if not (
            self.env.user.has_group('account.group_account_user')
            or self.env.user.has_group('sales_team.group_sale_salesman')
        ):
            raise AccessError(_('No tiene permiso para administrar vistas del reporte.'))

    @api.model
    def list_views(self, company_id=None):
        self._check_report_access()
        company_id = company_id or self.env.company.id
        domain = [
            '|',
            ('user_id', '=', self.env.user.id),
            ('is_system', '=', True),
            ('company_id', '=', company_id),
        ]
        views = self.search(domain, order='sequence, name')
        return [{
            'id': v.id,
            'name': v.name,
            'is_default': v.is_default,
            'is_system': v.is_system,
            'filters': json.loads(v.filter_json or '{}'),
        } for v in views]

    @api.model
    def save_view(self, name, filters, company_id=None, is_default=False):
        self._check_report_access()
        company_id = company_id or self.env.company.id
        payload = json.dumps(filters or {}, sort_keys=True)
        existing = self.search([
            ('name', '=', name),
            ('user_id', '=', self.env.user.id),
            ('company_id', '=', company_id),
        ], limit=1)
        if existing:
            existing.write({'filter_json': payload, 'is_default': is_default})
            rec = existing
        else:
            rec = self.create({
                'name': name,
                'user_id': self.env.user.id,
                'company_id': company_id,
                'filter_json': payload,
                'is_default': is_default,
            })
        if is_default:
            others = self.search([
                ('user_id', '=', self.env.user.id),
                ('company_id', '=', company_id),
                ('id', '!=', rec.id),
            ])
            others.write({'is_default': False})
        return {'id': rec.id, 'name': rec.name}

    @api.model
    def rename_view(self, view_id, name):
        self._check_report_access()
        view = self.browse(view_id)
        if not view or view.user_id != self.env.user:
            raise AccessError(_('No puede modificar esta vista.'))
        if view.is_system:
            raise UserError(_('Las vistas del sistema no se pueden renombrar.'))
        view.name = name
        return True

    @api.model
    def delete_view(self, view_id):
        self._check_report_access()
        view = self.browse(view_id)
        if not view or view.user_id != self.env.user:
            raise AccessError(_('No puede eliminar esta vista.'))
        if view.is_system:
            raise UserError(_('Las vistas del sistema no se pueden eliminar.'))
        view.unlink()
        return True

    @api.model
    def ensure_system_views(self):
        """Crea vistas rápidas predeterminadas por compañía si no existen."""
        presets = [
            ('Pagos del mes', {'payment_period': 'this_month', 'show_pending_invoices': False}),
            ('Facturas pendientes', {'payment_state': 'not_paid', 'show_pending_invoices': True}),
            ('Pagos parciales', {'payment_state': 'partial'}),
            ('Facturas vencidas', {'overdue_only': True, 'show_pending_invoices': True}),
            ('Ventas a crédito', {'credit_term_filter': 'outside'}),
            ('Cobros por asesor', {'view_mode': 'by_payment'}),
            ('Clientes con mayor atraso', {'overdue_only': True, 'active_tab': 'overdue'}),
        ]
        for company in self.env.companies:
            for seq, (name, filters) in enumerate(presets, start=1):
                exists = self.search([
                    ('name', '=', name),
                    ('is_system', '=', True),
                    ('company_id', '=', company.id),
                ], limit=1)
                if not exists:
                    self.create({
                        'name': name,
                        'user_id': self.env.ref('base.user_admin').id,
                        'company_id': company.id,
                        'is_system': True,
                        'sequence': seq * 10,
                        'filter_json': json.dumps(filters),
                    })
