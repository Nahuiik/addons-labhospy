# -*- coding: utf-8 -*-
"""Modelos persistentes: layouts personalizados y acciones sobre alertas."""

import json
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseDashboardLayout(models.Model):
    _name = 'purchase.dashboard.layout'
    _description = 'Layout personalizado del dashboard de compras'
    _order = 'is_default desc, sequence, name'

    name = fields.Char(required=True, default=lambda self: _('Principal'))
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    is_default = fields.Boolean(default=False)
    is_shared = fields.Boolean(string='Compartido', default=False)
    share_token = fields.Char(copy=False, index=True)
    shared_from_user_id = fields.Many2one('res.users', string='Compartido por', ondelete='set null')
    layout_json = fields.Text(string='Layout JSON', default='{}')

    _sql_constraints = [
        (
            'user_company_name_uniq',
            'unique(user_id, company_id, name)',
            'Ya existe un layout con ese nombre para este usuario y compañía.',
        ),
    ]

    @api.model
    def _default_layout_payload(self):
        return {
            'widgets': [],
            'hidden': [],
            'pinned': [],
            'favorites': [],
            'heatmapDimension': 'month_vendor',
        }

    @api.model
    def _parse_layout(self, layout_json):
        try:
            data = json.loads(layout_json or '{}')
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        defaults = self._default_layout_payload()
        return {**defaults, **data}

    @api.model
    def _get_or_create_default(self, user, company):
        rec = self.search([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
            ('is_default', '=', True),
        ], limit=1)
        if rec:
            return rec
        rec = self.search([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
        ], limit=1, order='id')
        if rec:
            rec.is_default = True
            return rec
        return self.create({
            'name': _('Principal'),
            'user_id': user.id,
            'company_id': company.id,
            'is_default': True,
            'layout_json': json.dumps(self._default_layout_payload()),
        })

    @api.model
    def list_for_user(self):
        user = self.env.user
        company = self.env.company
        layouts = self.search([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
        ])
        if not layouts:
            layouts = self._get_or_create_default(user, company)
        return [{
            'id': l.id,
            'name': l.name,
            'is_default': l.is_default,
            'is_shared': l.is_shared,
            'share_token': l.share_token or False,
            'shared_from': l.shared_from_user_id.name if l.shared_from_user_id else False,
        } for l in layouts]

    @api.model
    def get_layout(self, layout_id=None):
        user = self.env.user
        company = self.env.company
        if layout_id:
            rec = self.browse(layout_id).exists()
            if not rec or rec.user_id != user or rec.company_id != company:
                raise UserError(_('Layout no encontrado.'))
        else:
            rec = self._get_or_create_default(user, company)
        return {'id': rec.id, 'layout': self._parse_layout(rec.layout_json)}

    @api.model
    def save_layout(self, layout_id=None, layout=None, name=None):
        user = self.env.user
        company = self.env.company
        layout = layout or {}
        if layout_id:
            rec = self.browse(layout_id).exists()
            if not rec or rec.user_id != user or rec.company_id != company:
                raise UserError(_('Layout no encontrado.'))
        else:
            rec = self._get_or_create_default(user, company)
        existing = self._parse_layout(rec.layout_json)
        merged = {**existing, **layout}
        rec.layout_json = json.dumps(merged)
        if name:
            rec.name = name
        return {'success': True, 'id': rec.id, 'layout': merged}

    @api.model
    def create_layout(self, name, copy_from_id=None):
        user = self.env.user
        company = self.env.company
        payload = self._default_layout_payload()
        if copy_from_id:
            src = self.browse(copy_from_id).exists()
            if src and src.user_id == user and src.company_id == company:
                payload = self._parse_layout(src.layout_json)
        rec = self.create({
            'name': name or _('Nuevo dashboard'),
            'user_id': user.id,
            'company_id': company.id,
            'layout_json': json.dumps(payload),
        })
        return {'success': True, 'id': rec.id, 'name': rec.name}

    @api.model
    def delete_layout(self, layout_id):
        rec = self.browse(layout_id).exists()
        if not rec or rec.user_id != self.env.user:
            raise UserError(_('Layout no encontrado.'))
        if rec.is_default:
            raise UserError(_('No puede eliminar el layout predeterminado.'))
        rec.unlink()
        return {'success': True}

    @api.model
    def set_default_layout(self, layout_id):
        user = self.env.user
        company = self.env.company
        rec = self.browse(layout_id).exists()
        if not rec or rec.user_id != user or rec.company_id != company:
            raise UserError(_('Layout no encontrado.'))
        others = self.search([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
            ('id', '!=', rec.id),
        ])
        others.write({'is_default': False})
        rec.is_default = True
        return {'success': True}

    @api.model
    def restore_default_layout(self, layout_id=None):
        user = self.env.user
        company = self.env.company
        if layout_id:
            rec = self.browse(layout_id).exists()
        else:
            rec = self._get_or_create_default(user, company)
        if not rec or rec.user_id != user:
            raise UserError(_('Layout no encontrado.'))
        rec.layout_json = json.dumps(self._default_layout_payload())
        return {'success': True, 'layout': self._parse_layout(rec.layout_json)}

    @api.model
    def share_layout(self, layout_id):
        rec = self.browse(layout_id).exists()
        if not rec or rec.user_id != self.env.user:
            raise UserError(_('Layout no encontrado.'))
        if not rec.share_token:
            rec.share_token = uuid.uuid4().hex
        rec.is_shared = True
        return {'success': True, 'share_token': rec.share_token}

    @api.model
    def import_shared_layout(self, share_token, name=None):
        src = self.search([('share_token', '=', share_token), ('is_shared', '=', True)], limit=1)
        if not src:
            raise UserError(_('Layout compartido no encontrado.'))
        user = self.env.user
        company = self.env.company
        payload = self._parse_layout(src.layout_json)
        rec = self.create({
            'name': name or _('%s (compartido)', src.name),
            'user_id': user.id,
            'company_id': company.id,
            'shared_from_user_id': src.user_id.id,
            'layout_json': json.dumps(payload),
        })
        return {'success': True, 'id': rec.id, 'layout': payload}


class PurchaseDashboardAlertAction(models.Model):
    _name = 'purchase.dashboard.alert.action'
    _description = 'Acción de usuario sobre alerta del dashboard de compras'
    _order = 'write_date desc'

    alert_key = fields.Char(required=True, index=True)
    title = fields.Char()
    severity = fields.Selection([
        ('critical', 'Crítica'),
        ('high', 'Alta'),
        ('warning', 'Media'),
        ('info', 'Baja'),
    ], default='info')
    state = fields.Selection([
        ('new', 'Nueva'),
        ('read', 'Leída'),
        ('ignored', 'Ignorada'),
        ('resolved', 'Resuelta'),
    ], default='new', index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade', index=True)
    assignee_id = fields.Many2one('res.users', string='Responsable', ondelete='set null')
    deadline = fields.Date(string='Fecha límite')
    comment = fields.Text()
    history_json = fields.Text(default='[]')

    _sql_constraints = [
        (
            'alert_user_company_uniq',
            'unique(alert_key, user_id, company_id)',
            'La alerta ya fue registrada para este usuario.',
        ),
    ]

    @api.model
    def _append_history(self, rec, message, author=None):
        try:
            history = json.loads(rec.history_json or '[]')
        except ValueError:
            history = []
        history.append({
            'at': fields.Datetime.to_string(fields.Datetime.now()),
            'author': author or self.env.user.name,
            'message': message,
        })
        rec.history_json = json.dumps(history[-50:])

    @api.model
    def upsert_alert(self, alert_key, values=None):
        values = values or {}
        user = self.env.user
        company = self.env.company
        rec = self.search([
            ('alert_key', '=', alert_key),
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if rec:
            rec.write(values)
        else:
            rec = self.create({
                'alert_key': alert_key,
                'user_id': user.id,
                'company_id': company.id,
                **values,
            })
        return rec

    @api.model
    def update_alert(self, alert_key, action, payload=None):
        payload = payload or {}
        rec = self.upsert_alert(alert_key, {
            'title': payload.get('title'),
            'severity': payload.get('severity') or 'info',
        })
        messages = {
            'read': _('Marcada como leída'),
            'ignore': _('Alerta ignorada'),
            'resolve': _('Alerta resuelta'),
            'assign': _('Responsable asignado'),
            'comment': _('Comentario agregado'),
            'deadline': _('Fecha límite actualizada'),
        }
        if action == 'read':
            rec.state = 'read'
        elif action == 'ignore':
            rec.state = 'ignored'
        elif action == 'resolve':
            rec.state = 'resolved'
        elif action == 'assign':
            rec.assignee_id = payload.get('assignee_id') or False
        elif action == 'deadline':
            rec.deadline = payload.get('deadline') or False
        elif action == 'comment':
            rec.comment = payload.get('comment') or rec.comment
        self._append_history(rec, messages.get(action, action))
        if payload.get('comment') and action != 'comment':
            self._append_history(rec, payload['comment'])
        return {'success': True, 'state': rec.state}
