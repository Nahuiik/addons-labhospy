# -*- coding: utf-8 -*-
import logging
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

BUS_CHANNEL = 'gn_due_alert_notification'

LEVEL_PRIORITY = {
    'soon': 10,
    'today': 20,
    'overdue': 30,
    'critical': 40,
}

PAYABLE_MOVE_TYPES = ('in_invoice',)
RECEIVABLE_INVOICE_MOVE_TYPES = ('out_invoice',)


class GnDueAlertEngine(models.AbstractModel):
    _name = 'gn.due.alert.engine'
    _description = 'Motor de evaluacion de alertas de vencimiento'

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @api.model
    def _fmt_amount(self, amount, currency):
        return formatLang(self.env, amount, currency_obj=currency)

    @api.model
    def _open_moves_domain(self, company, alert_kind):
        move_types = (
            PAYABLE_MOVE_TYPES if alert_kind == 'payable'
            else RECEIVABLE_INVOICE_MOVE_TYPES)
        return [
            ('company_id', '=', company.id),
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'reversed')),
            ('amount_residual', '>', 0),
            ('invoice_date_due', '!=', False),
        ]

    @api.model
    def _open_receivable_lines_domain(self, company):
        """Apuntes CxC abiertos en asientos (saldos iniciales MISCE, etc.)."""
        return [
            ('company_id', '=', company.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('partner_id', '!=', False),
            ('reconciled', '=', False),
            ('amount_residual', '>', 0),
            ('move_id.move_type', '=', 'entry'),
        ]

    @api.model
    def _line_ref_date(self, line):
        return line.date_maturity or line.move_id.date

    @api.model
    def _line_residual(self, line):
        return abs(line.amount_residual)

    @api.model
    def _receivable_line_ref(self, line):
        move = line.move_id
        ref = (move.ref or move.name or '').strip()
        account = line.account_id.code or ''
        label = (line.name or '').strip()
        if ref:
            base = ref
        elif label:
            base = label
        else:
            base = move.name or _('Saldo CxC')
        if account:
            return '%s (%s)' % (base, account)
        return base

    @api.model
    def _invoice_alert_line(self, move, alert_kind):
        acc_type = (
            'liability_payable' if alert_kind == 'payable'
            else 'asset_receivable')
        return move.line_ids.filtered(
            lambda l: l.account_id.account_type == acc_type
            and l.partner_id
            and not l.reconciled
            and abs(l.amount_residual) > 0
        )[:1]

    @api.model
    def _is_kind_enabled(self, company, alert_kind):
        if alert_kind == 'payable':
            return getattr(company, 'due_alert_enabled', False)
        return getattr(company, 'customer_due_alert_enabled', False)

    @api.model
    def _get_level(self, days, company):
        soon_days = company.gn_due_notif_days_before or 3
        if days < 0:
            critical_days = company.gn_due_notif_critical_days or 15
            if abs(days) >= critical_days:
                return 'critical'
            return 'overdue'
        if days == 0:
            return 'today'
        if days <= soon_days:
            return 'soon'
        return False

    @api.model
    def _get_recipient_users_for_line(self, line, company, alert_kind):
        move = line.move_id
        users = self.env['res.users']
        if move.invoice_user_id and move.invoice_user_id.active:
            users |= move.invoice_user_id
        if company.gn_due_notif_default_responsible_id.active:
            users |= company.gn_due_notif_default_responsible_id
        group_xml = (
            'gn_invoice_due_alerts.group_invoice_due_alert_user'
            if alert_kind == 'payable'
            else 'gn_customer_due_alerts.group_customer_due_alert_user')
        group = self.env.ref(group_xml, raise_if_not_found=False)
        if group:
            users |= group.all_user_ids.filtered(lambda u: u.active)
        if company.gn_due_notif_notify_account_admins:
            admin_group = self.env.ref(
                'account.group_account_manager', raise_if_not_found=False)
            if admin_group:
                users |= admin_group.all_user_ids.filtered(lambda u: u.active)
        extra = company.gn_due_notif_recipient_user_ids.filtered(
            lambda u: u.active)
        users |= extra
        result = self.env['res.users']
        for user in users:
            try:
                if company.id not in user.company_ids.ids:
                    continue
                if not line.with_user(user).has_access('read'):
                    continue
                result |= user
            except Exception:
                continue
        return result

    @api.model
    def _should_notify_now(self, notification, company):
        if not company.gn_due_notif_realtime_enabled:
            return False
        if notification.state in ('closed', 'resolved'):
            return False
        if notification.state == 'snoozed':
            if (notification.snoozed_until
                    and fields.Datetime.now() < notification.snoozed_until):
                return False
        if not notification.last_notified_at:
            return True
        repeat_hours = company.gn_due_notif_repeat_hours or 24
        next_time = notification.last_notified_at + relativedelta(
            hours=repeat_hours)
        return fields.Datetime.now() >= next_time

    # ------------------------------------------------------------------
    # Resumen diario por correo (hora configurada)
    # ------------------------------------------------------------------
    @api.model
    def _should_send_daily_summary(self, company):
        if not company.gn_due_notif_daily_summary_enabled:
            return True
        today = fields.Date.context_today(self.with_company(company))
        if company.gn_due_notif_last_daily_summary_date == today:
            return False
        tz_company = company.partner_id.tz or 'UTC'
        now_local = fields.Datetime.context_timestamp(
            self.with_company(company).with_context(tz=tz_company),
            fields.Datetime.now())
        target_hour = int(company.gn_due_notif_daily_summary_hour or 8)
        return now_local.hour >= target_hour

    @api.model
    def _mark_daily_summary_sent(self, company):
        today = fields.Date.context_today(self.with_company(company))
        # SUDO-JUSTIFIED: campo tecnico de cron; el usuario no escribe esta marca diaria.
        company.sudo().write({'gn_due_notif_last_daily_summary_date': today})

    # ------------------------------------------------------------------
    # Bus
    # ------------------------------------------------------------------
    @api.model
    def _push_bus_updates(self, notifications):
        Notification = self.env['gn.due.alert.notification']
        seen = set()
        for notif in notifications:
            key = (notif.user_id.id, notif.company_id.id)
            if key in seen:
                continue
            seen.add(key)
            user = notif.user_id
            company = notif.company_id
            if not user.partner_id:
                continue
            payload = Notification._build_user_notifications_payload(
                user, company, limit=50)
            self.env['bus.bus']._sendone(
                user.partner_id, BUS_CHANNEL, payload)

    @api.model
    def _notify_user(self, notification, company):
        notification.write({
            'state': 'sent',
            'last_notified_at': fields.Datetime.now(),
            'notify_count': notification.notify_count + 1,
        })
        notification._log_action('notify', _('Notificacion enviada'))
        self._push_bus_updates(notification)

    # ------------------------------------------------------------------
    # Evaluacion por apunte contable
    # ------------------------------------------------------------------
    @api.model
    def _evaluate_line_for_users(
            self, line, alert_kind, company, today, source_type):
        ref_date = (
            line.move_id.invoice_date_due
            if source_type == 'invoice' and line.move_id.invoice_date_due
            else self._line_ref_date(line))
        if not ref_date:
            return None
        days = (ref_date - today).days
        level = self._get_level(days, company)
        if not level:
            return None
        users = self._get_recipient_users_for_line(line, company, alert_kind)
        if not users:
            return None
        # SUDO-JUSTIFIED: motor cron crea/actualiza alertas para multiples destinatarios.
        Notification = self.env['gn.due.alert.notification'].sudo()
        line_id = line.id
        created_or_updated = Notification.browse()
        existing_by_user = {
            n.user_id.id: n
            for n in Notification.search([
                ('move_line_id', '=', line_id),
                ('user_id', 'in', users.ids),
            ])
        }
        for user in users:
            notif = existing_by_user.get(user.id)
            vals = {
                'move_id': line.move_id.id,
                'move_line_id': line_id,
                'source_type': source_type,
                'user_id': user.id,
                'company_id': company.id,
                'alert_kind': alert_kind,
                'alert_level': level,
                'days_delta': days,
                'priority': LEVEL_PRIORITY.get(level, 10),
                'date_due': ref_date,
                'amount_residual': self._line_residual(line),
            }
            if notif:
                old_level = notif.alert_level
                if notif.state in ('resolved', 'closed'):
                    continue
                if notif.state == 'snoozed':
                    if (notif.snoozed_until
                            and fields.Datetime.now() < notif.snoozed_until
                            and old_level == level):
                        continue
                    if (notif.snoozed_until
                            and fields.Datetime.now() >= notif.snoozed_until):
                        notif.state = 'pending'
                update_vals = dict(vals)
                if old_level != level:
                    update_vals['state'] = 'pending'
                    notif._log_action(
                        'level_change', _('%s -> %s') % (old_level, level))
                    if level == 'critical':
                        line.move_id._gn_due_alert_post_chatter(
                            _('Alerta critica generada (%s)') % level)
                notif.write(update_vals)
            else:
                notif = Notification.create({
                    **vals,
                    'state': 'pending',
                })
                notif._log_action('create', _('Alerta creada'))
            created_or_updated |= notif
            if self._should_notify_now(notif, company):
                self._notify_user(notif, company)
        return line_id

    @api.model
    def _evaluate_move_for_users(self, move, alert_kind, company, today):
        line = self._invoice_alert_line(move, alert_kind)
        if not line:
            return None
        return self._evaluate_line_for_users(
            line, alert_kind, company, today, 'invoice')

    @api.model
    def _resolve_stale_notifications(
            self, company, alert_kind, open_line_ids, source_types):
        # SUDO-JUSTIFIED: cron cierra alertas obsoletas fuera del ACL del destinatario.
        Notification = self.env['gn.due.alert.notification'].sudo()
        stale = Notification.search([
            ('company_id', '=', company.id),
            ('alert_kind', '=', alert_kind),
            ('source_type', 'in', source_types),
            ('state', 'not in', ('resolved',)),
            ('move_line_id', 'not in', open_line_ids or [0]),
        ])
        for notif in stale:
            line = notif.move_line_id
            move = notif.move_id
            reason = 'manual'
            if line and (line.reconciled or line.amount_residual <= 0):
                reason = 'paid'
            elif move.payment_state == 'paid' or move.amount_residual <= 0:
                reason = 'paid'
            elif move.state == 'cancel':
                reason = 'cancelled'
            elif move.payment_state == 'reversed':
                reason = 'reversed'
            notif.write({
                'state': 'resolved',
                'resolved_at': fields.Datetime.now(),
                'resolution_reason': reason,
            })
            notif._log_action('resolve', _('Resuelta: %s') % reason)
            if reason == 'paid':
                move._gn_due_alert_post_chatter(
                    _('Alerta resuelta por pago'))
        if stale:
            self._push_bus_updates(stale)

    @api.model
    def _evaluate_invoices(self, company, alert_kind, batch_size=200):
        today = fields.Date.context_today(self.with_company(company))
        domain = self._open_moves_domain(company, alert_kind)
        # SUDO-JUSTIFIED: cron evalua facturas abiertas de todos los usuarios destino.
        Move = self.env['account.move'].sudo()
        offset = 0
        processed = 0
        open_line_ids = []
        while True:
            moves = Move.search(
                domain, order='id', limit=batch_size, offset=offset)
            if not moves:
                break
            for move in moves:
                try:
                    line_id = self._evaluate_move_for_users(
                        move, alert_kind, company, today)
                    if line_id:
                        open_line_ids.append(line_id)
                    processed += 1
                except Exception:
                    _logger.exception(
                        'Error evaluando alerta move_id=%s company=%s',
                        move.id, company.id)
            offset += batch_size
        return processed, open_line_ids

    @api.model
    def _evaluate_receivable_entries(self, company, batch_size=200):
        today = fields.Date.context_today(self.with_company(company))
        domain = self._open_receivable_lines_domain(company)
        # SUDO-JUSTIFIED: cron evalua apuntes CxC abiertos sin restriccion por usuario.
        Line = self.env['account.move.line'].sudo()
        offset = 0
        processed = 0
        open_line_ids = []
        while True:
            lines = Line.search(
                domain, order='id', limit=batch_size, offset=offset)
            if not lines:
                break
            for line in lines:
                try:
                    line_id = self._evaluate_line_for_users(
                        line, 'receivable', company, today, 'receivable_line')
                    if line_id:
                        open_line_ids.append(line_id)
                    processed += 1
                except Exception:
                    _logger.exception(
                        'Error evaluando apunte line_id=%s company=%s',
                        line.id, company.id)
            offset += batch_size
        return processed, open_line_ids

    @api.model
    def _evaluate_kind(self, company, alert_kind, batch_size=200):
        if not self._is_kind_enabled(company, alert_kind):
            return 0
        if not company.gn_due_notif_enabled:
            return 0
        processed, open_line_ids = self._evaluate_invoices(
            company, alert_kind, batch_size=batch_size)
        source_types = ['invoice']
        if alert_kind == 'receivable':
            extra, entry_line_ids = self._evaluate_receivable_entries(
                company, batch_size=batch_size)
            processed += extra
            open_line_ids.extend(entry_line_ids)
            source_types.append('receivable_line')
        self._resolve_stale_notifications(
            company, alert_kind, open_line_ids, source_types)
        return processed

    @api.model
    def cron_evaluate_due_alerts(self):
        from odoo.addons.gn_due_alert_notifications.hooks import _set_cron_intervals
        _set_cron_intervals(self.env)
        self.cron_migrate_notification_lines()
        total = 0
        for company in self.env['res.company'].search([]):
            try:
                with self.env.cr.savepoint():
                    total += self._evaluate_kind(company, 'payable')
                    total += self._evaluate_kind(company, 'receivable')
            except Exception:
                _logger.exception(
                    'Error cron alertas compania %s', company.name)
        return total

    @api.model
    def action_snooze_notification(self, notification_id):
        notif = self.env['gn.due.alert.notification'].browse(notification_id)
        notif.action_snooze()
        return self.get_initial_payload()

    @api.model
    def action_review_notification(self, notification_id):
        notif = self.env['gn.due.alert.notification'].browse(notification_id)
        notif.action_mark_reviewed()
        return self.get_initial_payload()

    @api.model
    def action_close_notification(self, notification_id):
        notif = self.env['gn.due.alert.notification'].browse(notification_id)
        notif.action_close()
        return self.get_initial_payload()

    @api.model
    def action_open_invoice(self, notification_id):
        notif = self.env['gn.due.alert.notification'].browse(notification_id)
        return notif.action_open_invoice()

    @api.model
    def action_register_payment(self, notification_id):
        notif = self.env['gn.due.alert.notification'].browse(notification_id)
        return notif.action_register_payment()

    @api.model
    def get_initial_payload(self):
        if not self.env.user.has_group(
                'gn_due_alert_notifications.group_due_alert_notif_user'):
            return {'cards': [], 'pending_count': 0, 'max_visible': 5}
        return self.env['gn.due.alert.notification'].get_user_notifications_payload()

    @api.model
    def cron_migrate_notification_lines(self):
        """Rellena move_line_id en alertas antiguas (post-actualizacion)."""
        # SUDO-JUSTIFIED: migracion tecnica post-actualizacion ejecutada por cron.
        Notification = self.env['gn.due.alert.notification'].sudo()
        pending = Notification.search([
            ('move_line_id', '=', False),
            ('move_id', '!=', False),
        ])
        for notif in pending:
            line = self._invoice_alert_line(notif.move_id, notif.alert_kind)
            if line:
                notif.move_line_id = line.id
        return len(pending)
