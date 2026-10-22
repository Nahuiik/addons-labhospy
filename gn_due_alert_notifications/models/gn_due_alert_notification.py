# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


ALERT_KINDS = [
    ('payable', 'Cuentas por pagar'),
    ('receivable', 'Cuentas por cobrar'),
]

ALERT_LEVELS = [
    ('soon', 'Proxima a vencer'),
    ('today', 'Vence hoy'),
    ('overdue', 'Vencida'),
    ('critical', 'Vencida critica'),
]

ALERT_STATES = [
    ('pending', 'Pendiente'),
    ('sent', 'Enviada'),
    ('reviewed', 'Revisada'),
    ('snoozed', 'Pospuesta'),
    ('closed', 'Cerrada'),
    ('resolved', 'Resuelta'),
]

SOURCE_TYPES = [
    ('invoice', 'Factura'),
    ('receivable_line', 'Saldo CxC (apunte)'),
]

LEVEL_LABELS = {
    'soon': _('Factura proxima a vencer'),
    'today': _('Factura vence hoy'),
    'overdue': _('Factura vencida'),
    'critical': _('Factura vencida critica'),
}

LINE_LEVEL_LABELS = {
    'soon': _('Saldo CxC proximo a vencer'),
    'today': _('Saldo CxC vence hoy'),
    'overdue': _('Saldo CxC vencido'),
    'critical': _('Saldo CxC vencido critico'),
}

KIND_LABELS = {
    'payable': _('CUENTAS POR PAGAR'),
    'receivable': _('CUENTAS POR COBRAR'),
}


class GnDueAlertNotification(models.Model):
    _name = 'gn.due.alert.notification'
    _description = 'Alerta de vencimiento de factura'
    _order = 'priority desc, date_due asc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(compute='_compute_name', store=True)
    move_id = fields.Many2one(
        'account.move', string='Documento', required=True, index=True,
        ondelete='cascade', check_company=True)
    move_line_id = fields.Many2one(
        'account.move.line', string='Apunte contable', index=True,
        ondelete='cascade', check_company=True)
    source_type = fields.Selection(
        selection=SOURCE_TYPES, string='Origen', default='invoice',
        required=True, index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Contacto', index=True,
        compute='_compute_partner_amounts', store=True)
    user_id = fields.Many2one(
        'res.users', string='Destinatario', required=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    alert_kind = fields.Selection(
        selection=ALERT_KINDS, string='Tipo', required=True, index=True)
    alert_level = fields.Selection(
        selection=ALERT_LEVELS, string='Nivel', required=True, index=True)
    state = fields.Selection(
        selection=ALERT_STATES, string='Estado', default='pending',
        required=True, index=True, tracking=True)
    priority = fields.Integer(default=10, index=True)

    invoice_date = fields.Date(
        compute='_compute_partner_amounts', store=True)
    date_due = fields.Date(
        string='Vencimiento', index=True,
        compute='_compute_partner_amounts', store=True)
    days_delta = fields.Integer(
        string='Dias', help='Positivo = por vencer, negativo = vencidos')
    amount_total = fields.Monetary(
        compute='_compute_partner_amounts', store=True,
        currency_field='currency_id')
    amount_residual = fields.Monetary(
        compute='_compute_partner_amounts', store=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_partner_amounts', store=True)
    responsible_id = fields.Many2one(
        'res.users', string='Responsable de pago',
        related='move_id.invoice_user_id', store=True)
    message = fields.Text(string='Mensaje')

    generated_at = fields.Datetime(
        string='Generada', default=fields.Datetime.now, required=True)
    last_notified_at = fields.Datetime(string='Ultima notificacion')
    next_notify_at = fields.Datetime(string='Proxima notificacion', index=True)
    notify_count = fields.Integer(string='Veces notificada', default=0)

    reviewed_at = fields.Datetime(string='Revisada el')
    reviewed_by_id = fields.Many2one('res.users', string='Revisada por')
    closed_at = fields.Datetime(string='Cerrada el')
    closed_by_id = fields.Many2one('res.users', string='Cerrada por')
    snoozed_until = fields.Datetime(string='Pospuesta hasta')
    resolved_at = fields.Datetime(string='Resuelta el')
    resolution_reason = fields.Selection(
        selection=[
            ('paid', 'Pagada / regularizada'),
            ('cancelled', 'Cancelada'),
            ('reversed', 'Revertida'),
            ('due_changed', 'Cambio de vencimiento'),
            ('manual', 'Manual'),
        ],
        string='Motivo de resolucion')

    log_ids = fields.One2many(
        'gn.due.alert.notification.log', 'notification_id', string='Historial')

    _move_line_user_uniq = models.Constraint(
        'unique(move_line_id, user_id)',
        'Ya existe una alerta para este apunte y usuario.',
    )

    @api.depends(
        'move_line_id', 'move_id', 'source_type',
        'move_line_id.partner_id', 'move_id.partner_id',
        'move_line_id.amount_residual', 'move_id.amount_total',
        'move_line_id.currency_id', 'move_id.currency_id',
        'move_id.invoice_date', 'move_id.invoice_date_due',
        'move_line_id.date_maturity', 'date_due',
    )
    def _compute_partner_amounts(self):
        for rec in self:
            line = rec.move_line_id
            move = rec.move_id
            if line:
                rec.partner_id = line.partner_id
                rec.amount_residual = abs(line.amount_residual)
                rec.currency_id = line.currency_id or move.currency_id
                rec.invoice_date = move.invoice_date or line.date
                rec.date_due = (
                    line.date_maturity
                    or move.invoice_date_due
                    or line.date)
                rec.amount_total = (
                    move.amount_total if move.move_type != 'entry'
                    else abs(line.amount_residual))
            else:
                rec.partner_id = move.partner_id
                rec.amount_total = move.amount_total
                rec.amount_residual = move.amount_residual
                rec.currency_id = move.currency_id
                rec.invoice_date = move.invoice_date
                rec.date_due = move.invoice_date_due

    @api.depends('move_id', 'move_line_id', 'alert_kind', 'partner_id', 'source_type')
    def _compute_name(self):
        for rec in self:
            if rec.source_type == 'receivable_line' and rec.move_line_id:
                label = rec.env['gn.due.alert.engine']._receivable_line_ref(
                    rec.move_line_id)
            else:
                label = rec.move_id.display_name or rec.move_id.name or ''
            rec.name = '%s - %s' % (
                dict(ALERT_KINDS).get(rec.alert_kind, ''), label)

    def _check_notification_access(self):
        if not self.env.user.has_group(
                'gn_due_alert_notifications.group_due_alert_notif_user'):
            raise AccessError(_('No tiene permiso para gestionar alertas.'))

    def _log_action(self, action, note=''):
        # SUDO-JUSTIFIED: bitacora de auditoria; el usuario destino no crea estos registros.
        self.env['gn.due.alert.notification.log'].sudo().create({
            'notification_id': self.id,
            'user_id': self.env.user.id,
            'action': action,
            'note': note,
        })

    def action_open_invoice(self):
        self._check_notification_access()
        self.ensure_one()
        move = self.move_id
        if not move.with_user(self.env.user).has_access('read'):
            raise AccessError(_('No puede abrir este documento.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'views': [[False, 'form']],
            'target': 'current',
        }

    def action_register_payment(self):
        self._check_notification_access()
        self.ensure_one()
        if self.source_type == 'receivable_line':
            raise UserError(_(
                'Los saldos CxC de apuntes no tienen asistente de pago. '
                'Abra el asiento y registre el cobro desde alli.'))
        move = self.move_id
        if move.move_type not in ('in_invoice', 'out_invoice'):
            raise UserError(_('Este documento no admite registro de pago directo.'))
        if not move.with_user(self.env.user).has_access('write'):
            raise AccessError(_('No puede registrar pagos en esta factura.'))
        return move.action_register_payment()

    def action_snooze(self):
        self._check_notification_access()
        company = self.env.company
        days = company.gn_due_notif_snooze_days or 1
        now = fields.Datetime.now()
        snooze_until = now + relativedelta(days=days)
        for rec in self:
            rec.write({
                'state': 'snoozed',
                'snoozed_until': snooze_until,
                'next_notify_at': snooze_until,
            })
            rec._log_action('snooze', _('Pospuesta %d dia(s)') % days)
            rec.move_id._gn_due_alert_post_chatter(
                _('Alerta pospuesta por %s hasta %s') % (
                    self.env.user.name,
                    fields.Datetime.to_string(snooze_until),
                ))
        self.env['gn.due.alert.engine']._push_bus_updates(self)
        return True

    def action_mark_reviewed(self):
        self._check_notification_access()
        now = fields.Datetime.now()
        for rec in self:
            rec.write({
                'state': 'reviewed',
                'reviewed_at': now,
                'reviewed_by_id': self.env.user.id,
            })
            rec._log_action('review', _('Marcada como revisada'))
            rec.move_id._gn_due_alert_post_chatter(
                _('Alerta revisada por %s') % self.env.user.name)
        self.env['gn.due.alert.engine']._push_bus_updates(self)
        return True

    def action_close(self):
        self._check_notification_access()
        now = fields.Datetime.now()
        for rec in self:
            rec.write({
                'state': 'closed',
                'closed_at': now,
                'closed_by_id': self.env.user.id,
            })
            rec._log_action('close', _('Cerrada por el usuario'))
        self.env['gn.due.alert.engine']._push_bus_updates(self)
        return True

    def action_reopen(self):
        self._check_notification_access()
        for rec in self:
            if rec.state not in ('closed', 'reviewed'):
                continue
            rec.write({'state': 'sent'})
            rec._log_action('reopen', _('Reabierta'))
        self.env['gn.due.alert.engine']._push_bus_updates(self)
        return True

    @api.model
    def get_user_notifications_payload(self, limit=50):
        self._check_notification_access()
        return self._build_user_notifications_payload(
            self.env.user, self.env.company, limit=limit)

    @api.model
    def _build_user_notifications_payload(self, user, company, limit=50):
        max_visible = company.gn_due_notif_max_visible_cards or 5
        domain = [
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
            ('state', 'in', ('pending', 'sent', 'reviewed')),
        ]
        # SUDO-JUSTIFIED: payload bus de tarjetas propias; evita bloqueo por record rules.
        records = self.sudo().search(
            domain, order='priority desc, date_due asc', limit=limit)
        cards = [r._to_bus_payload() for r in records]
        pending_count = self.sudo().search_count([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
            ('state', 'in', ('pending', 'sent')),
        ])
        return {
            'cards': cards[:max_visible],
            'total_count': len(cards),
            'pending_count': pending_count,
            'max_visible': max_visible,
            'sound_enabled': company.gn_due_notif_sound_enabled,
        }

    def _level_labels(self):
        self.ensure_one()
        if self.source_type == 'receivable_line':
            return LINE_LEVEL_LABELS
        return LEVEL_LABELS

    def _to_bus_payload(self):
        self.ensure_one()
        move = self.move_id
        level = self.alert_level
        labels = self._level_labels()
        partner_name = self.partner_id.display_name or ''
        if self.source_type == 'receivable_line' and self.move_line_id:
            doc_name = self.env['gn.due.alert.engine']._receivable_line_ref(
                self.move_line_id)
        else:
            doc_name = move.name or move.ref or ''
        if level == 'soon' and self.days_delta > 0:
            if self.source_type == 'receivable_line':
                msg = _('Este saldo CxC vence en %d dias. Revise el cobro.') % self.days_delta
            else:
                msg = _('Esta factura vence en %d dias. Revise la programacion del pago.') % self.days_delta
        elif level == 'today':
            msg = (_('Este saldo CxC vence hoy. Revise el cobro.')
                   if self.source_type == 'receivable_line'
                   else _('Esta factura vence hoy. Revise la programacion del pago.'))
        elif level == 'critical':
            msg = _('Vencido hace %d dias (critico). Atencion urgente.') % abs(self.days_delta)
        elif level == 'overdue':
            msg = _('Vencido hace %d dias.') % abs(self.days_delta)
        else:
            msg = self.message or ''
        return {
            'id': self.id,
            'source_type': self.source_type,
            'can_register_payment': (
                self.source_type == 'invoice'
                and move.move_type in ('in_invoice', 'out_invoice')),
            'alert_kind': self.alert_kind,
            'kind_label': KIND_LABELS.get(self.alert_kind, ''),
            'alert_level': level,
            'level_label': labels.get(level, ''),
            'title': labels.get(level, ''),
            'move_id': move.id,
            'move_name': doc_name,
            'partner_name': partner_name,
            'invoice_date': (
                fields.Date.to_string(self.invoice_date)
                if self.invoice_date else ''),
            'date_due': (
                fields.Date.to_string(self.date_due)
                if self.date_due else ''),
            'days_delta': self.days_delta,
            'amount_total': self.amount_total,
            'amount_total_str': self.env['gn.due.alert.engine']._fmt_amount(
                self.amount_total, self.currency_id),
            'amount_residual': self.amount_residual,
            'amount_residual_str': self.env['gn.due.alert.engine']._fmt_amount(
                self.amount_residual, self.currency_id),
            'currency': self.currency_id.name or '',
            'company': self.company_id.name or '',
            'responsible': self.responsible_id.name or '',
            'message': msg,
            'state': self.state,
        }


class GnDueAlertNotificationLog(models.Model):
    _name = 'gn.due.alert.notification.log'
    _description = 'Historial de acciones de alerta'
    _order = 'create_date desc, id desc'

    notification_id = fields.Many2one(
        'gn.due.alert.notification', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Usuario', required=True)
    action = fields.Selection(
        selection=[
            ('create', 'Creada'),
            ('notify', 'Notificada'),
            ('snooze', 'Pospuesta'),
            ('review', 'Revisada'),
            ('close', 'Cerrada'),
            ('reopen', 'Reabierta'),
            ('resolve', 'Resuelta'),
            ('level_change', 'Cambio de nivel'),
        ],
        required=True)
    note = fields.Char()
