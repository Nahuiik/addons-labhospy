# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools.misc import formatLang, format_date

BUCKET_LABELS = {
    'overdue': 'Vencidas',
    'today': 'Vencen hoy',
    'soon': 'Proximas a vencer',
    'upcoming': 'Futuras',
}
BUCKET_ORDER = ['overdue', 'today', 'soon', 'upcoming']


class CustomerDueAlert(models.AbstractModel):
    """Servicio (sin tabla) que centraliza la logica del semaforo de cobros:
    clasificacion de facturas de cliente por vencimiento, datos para el
    tablero, correos y notificaciones emergentes."""
    _name = 'gn.customer.due.alert'
    _description = 'Servicio de alertas de vencimiento de facturas'

    # ------------------------------------------------------------------
    # Recoleccion / clasificacion
    # ------------------------------------------------------------------
    @api.model
    def _open_invoices_domain(self, company):
        return [
            ('company_id', '=', company.id),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('amount_residual', '>', 0),
            ('invoice_date_due', '!=', False),
        ]

    @api.model
    def _open_receivable_lines_domain(self, company):
        """Apuntes abiertos en CxC desde asientos (p. ej. saldos iniciales)."""
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
    def _open_receivable_lines(self, company):
        return self.env['account.move.line'].search(
            self._open_receivable_lines_domain(company),
            order='date_maturity asc, partner_id, id')

    @api.model
    def _line_residual(self, line):
        return abs(line.amount_residual)

    @api.model
    def _line_ref_date(self, line):
        return line.date_maturity or line.move_id.date

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
    def _bucket_for(self, days, soon_days):
        if days < 0:
            return 'overdue'
        if days == 0:
            return 'today'
        if days <= soon_days:
            return 'soon'
        return 'upcoming'

    @api.model
    def _collect(self, company, limit_per_bucket=500):
        """Devuelve la clasificacion completa para una compania."""
        today = fields.Date.context_today(self)
        soon_days = company.customer_due_alert_days_before or 3
        invoices = self.env['account.move'].search(
            self._open_invoices_domain(company), order='invoice_date_due asc')
        receivable_lines = self._open_receivable_lines(company)
        buckets = {k: [] for k in BUCKET_ORDER}
        totals = {k: 0.0 for k in BUCKET_ORDER}
        currency = company.currency_id
        for m in invoices:
            days = (m.invoice_date_due - today).days
            b = self._bucket_for(days, soon_days)
            totals[b] += abs(m.amount_residual_signed)
            if len(buckets[b]) < limit_per_bucket:
                buckets[b].append({
                    'id': m.id,
                    'source': 'invoice',
                    'name': self._customer_invoice_ref(m),
                    'partner': m.partner_id.display_name or '',
                    'date_due': self._fmt_date(m.invoice_date_due),
                    'days': days,
                    'residual': abs(m.amount_residual_signed),
                    'residual_str': formatLang(
                        self.env, abs(m.amount_residual_signed),
                        currency_obj=currency),
                })
        for line in receivable_lines:
            ref_date = self._line_ref_date(line)
            days = (ref_date - today).days
            b = self._bucket_for(days, soon_days)
            residual = self._line_residual(line)
            totals[b] += residual
            if len(buckets[b]) < limit_per_bucket:
                buckets[b].append({
                    'id': line.id,
                    'source': 'receivable_line',
                    'move_id': line.move_id.id,
                    'name': self._receivable_line_ref(line),
                    'partner': line.partner_id.display_name or '',
                    'date_due': self._fmt_date(ref_date),
                    'days': days,
                    'residual': residual,
                    'residual_str': formatLang(
                        self.env, residual, currency_obj=currency),
                })
        return {
            'today': today,
            'soon_days': soon_days,
            'currency': currency,
            'buckets': buckets,
            'totals': totals,
            'counts': {k: len(buckets[k]) for k in BUCKET_ORDER},
            'raw_counts': self._raw_counts(
                invoices, receivable_lines, today, soon_days),
        }

    @api.model
    def _raw_counts(self, invoices, receivable_lines, today, soon_days):
        counts = {k: 0 for k in BUCKET_ORDER}
        for m in invoices:
            days = (m.invoice_date_due - today).days
            counts[self._bucket_for(days, soon_days)] += 1
        for line in receivable_lines:
            ref_date = self._line_ref_date(line)
            days = (ref_date - today).days
            counts[self._bucket_for(days, soon_days)] += 1
        return counts

    # ------------------------------------------------------------------
    # Datos para el tablero OWL
    # ------------------------------------------------------------------
    @api.model
    def _check_user_access(self):
        if not self.env.user.has_group(
                'gn_customer_due_alerts.group_customer_due_alert_user'):
            raise AccessError(_(
                'No tiene permiso para ver las alertas de vencimiento.'))

    @api.model
    def _currency_payload(self, currency):
        return {
            'symbol': currency.symbol or '',
            'position': currency.position or 'before',
            'digits': currency.decimal_places,
        }

    @api.model
    def _fmt(self, amount, currency):
        return formatLang(self.env, amount, currency_obj=currency)

    @api.model
    def _fmt_date(self, value):
        """Fecha en formato dia/mes/anio (dd/MM/yyyy)."""
        if not value:
            return ''
        return format_date(self.env, value, date_format='dd/MM/yyyy')

    @api.model
    def _open_invoices(self, company):
        return self.env['account.move'].search(
            self._open_invoices_domain(company),
            order='invoice_date_due asc, partner_id')

    @api.model
    def _residual(self, move):
        return abs(move.amount_residual_signed)

    @api.model
    def _customer_invoice_ref(self, move):
        """Numero de factura del cliente."""
        ref = (move.name or move.ref or '').strip()
        return ref or _('Sin referencia de cliente')

    @api.model
    def _due_today_summary(self, invoices, today, currency):
        """Resumen en texto de facturas que vencen hoy (days == 0)."""
        items = []
        for m in invoices:
            if (m.invoice_date_due - today).days != 0:
                continue
            residual = self._residual(m)
            items.append({
                'partner': m.partner_id.display_name or '',
                'name': self._customer_invoice_ref(m),
                'residual': residual,
                'residual_str': self._fmt(residual, currency),
            })
        count = len(items)
        total = sum(i['residual'] for i in items)
        total_str = self._fmt(total, currency)
        if not count:
            text = _('Hoy no hay facturas de cliente que venzan.')
        else:
            header = _(
                'Hoy vencen %(count)d factura(s) por un total de %(total)s:'
            ) % {'count': count, 'total': total_str}
            detail = '\n'.join(
                _('• %(partner)s — %(bill)s — %(amount)s') % {
                    'partner': it['partner'],
                    'bill': it['name'],
                    'amount': it['residual_str'],
                }
                for it in items
            )
            text = header + '\n' + detail
        return {
            'count': count,
            'total': total,
            'total_str': total_str,
            'items': items,
            'text': text,
        }

    # --- Clasificacion tablero 1: semaforo de vencimientos ---
    @api.model
    def _due_traffic_bucket(self, days):
        """Clasifica por dias para vencer (negativo = vencida)."""
        if days == 0 or days > 15:
            return 'al_dia'
        if 1 <= days <= 7 or -7 <= days <= -1:
            return 'due_1_7'
        if 8 <= days <= 15 or -15 <= days <= -8:
            return 'due_8_15'
        return 'overdue_15'

    DUE_TRAFFIC_LABELS = {
        'al_dia': 'Al dia',
        'due_1_7': 'Por vencer (1-7 dias)',
        'due_8_15': 'Por vencer (8-15 dias)',
        'overdue_15': 'Vencida (>15 dias)',
    }
    DUE_TRAFFIC_ORDER = ['al_dia', 'due_1_7', 'due_8_15', 'overdue_15']

    # --- Clasificacion tablero 2: antiguedad por cliente ---
    @api.model
    def _aging_days(self, due_date, today):
        return max(0, (today - due_date).days)

    @api.model
    def _aging_bucket(self, age_days):
        if age_days <= 30:
            return 'b0_30'
        if age_days <= 60:
            return 'b31_60'
        if age_days <= 90:
            return 'b61_90'
        return 'b90_plus'

    AGING_LABELS = {
        'b0_30': 'Al dia (0-30)',
        'b31_60': 'Atencion (31-60)',
        'b61_90': 'En riesgo (61-90)',
        'b90_plus': 'Critico (+90)',
    }
    AGING_ORDER = ['b0_30', 'b31_60', 'b61_90', 'b90_plus']
    AGING_RANGES = {
        'b0_30': '0-30 dias',
        'b31_60': '31-60 dias',
        'b61_90': '61-90 dias',
        'b90_plus': '+90 dias',
    }
    AGING_STATUS = {
        'b0_30': 'AL DIA',
        'b31_60': 'ATENCION',
        'b61_90': 'EN RIESGO',
        'b90_plus': 'CRITICO',
    }
    AGING_RANK = {'b0_30': 0, 'b31_60': 1, 'b61_90': 2, 'b90_plus': 3}

    @api.model
    def _cxc_partner_list_base_domain(self):
        return [
            ('company_id', '=', self.env.company.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('partner_id', '!=', False),
            ('reconciled', '=', False),
            ('amount_residual', '>', 0),
            ('move_id.move_type', 'in', ('out_invoice', 'out_refund', 'entry')),
        ]

    @api.model
    def _line_aging_ref_date(self, line):
        ref_date = line.date_maturity
        if not ref_date and line.move_id.move_type in ('out_invoice', 'out_refund'):
            ref_date = line.move_id.invoice_date_due
        if not ref_date:
            ref_date = line.move_id.date
        return ref_date

    @api.model
    def get_cxc_partner_list_dashboard(self, domain=None):
        """KPIs de antigüedad para la lista CxC abiertos por contacto (sin límite de paginación)."""
        self._check_user_access()
        company = self.env.company
        today = fields.Date.context_today(self)
        currency = company.currency_id
        full_domain = list(self._cxc_partner_list_base_domain())
        if domain:
            full_domain.extend(domain)
        lines = self.env['account.move.line'].search(full_domain)

        kpis = {k: {'count': 0, 'partners': set(), 'total': 0.0} for k in self.AGING_ORDER}
        partners = {}
        due_7_total = 0.0
        due_7_count = 0

        for line in lines:
            partner = line.partner_id
            ref_date = self._line_aging_ref_date(line)
            if not partner or not ref_date:
                continue
            residual = abs(line.amount_residual)
            age = self._aging_days(ref_date, today)
            bucket = self._aging_bucket(age)
            days_to_due = (ref_date - today).days

            kpis[bucket]['count'] += 1
            kpis[bucket]['total'] += residual
            kpis[bucket]['partners'].add(partner.id)

            if 0 < days_to_due <= 7:
                due_7_total += residual
                due_7_count += 1

            pid = partner.id
            if pid not in partners:
                partners[pid] = {
                    'id': pid,
                    'name': partner.display_name or '',
                    'max_age': 0,
                }
            if age > partners[pid]['max_age']:
                partners[pid]['max_age'] = age

        grand_total = sum(k['total'] for k in kpis.values())
        cards = {}
        for key in self.AGING_ORDER:
            cards[key] = {
                'label': self.AGING_LABELS[key],
                'short': self.AGING_STATUS[key],
                'range': self.AGING_RANGES[key],
                'partner_count': len(kpis[key]['partners']),
                'invoice_count': kpis[key]['count'],
                'total': kpis[key]['total'],
                'total_str': self._fmt(kpis[key]['total'], currency),
                'pct': round(
                    kpis[key]['total'] / grand_total * 100, 0) if grand_total else 0,
            }

        oldest = max(partners.values(), key=lambda x: x['max_age'], default=None)
        return {
            'company': company.name,
            'today': self._fmt_date(today),
            'currency': self._currency_payload(currency),
            'cards': cards,
            'summary': {
                'grand_total': grand_total,
                'grand_total_str': self._fmt(grand_total, currency),
                'partner_count': len(partners),
                'oldest_days': oldest['max_age'] if oldest else 0,
                'oldest_partner': oldest['name'] if oldest else '',
                'due_7_total': due_7_total,
                'due_7_total_str': self._fmt(due_7_total, currency),
                'due_7_count': due_7_count,
            },
            'distribution': [
                {'key': k, 'pct': cards[k]['pct'], 'label': self.AGING_LABELS[k]}
                for k in self.AGING_ORDER
            ],
        }

    @api.model
    def get_dashboard_data(self):
        self._check_user_access()
        company = self.env.company
        info = self._collect(company)
        currency = info['currency']
        buckets = {}
        for key in BUCKET_ORDER:
            buckets[key] = {
                'label': BUCKET_LABELS[key],
                'count': info['raw_counts'][key],
                'total': info['totals'][key],
                'total_str': formatLang(
                    self.env, info['totals'][key], currency_obj=currency),
                'bills': info['buckets'][key],
            }
        grand_total = sum(info['totals'].values())
        return {
            'company': company.name,
            'today': self._fmt_date(info['today']),
            'soon_days': info['soon_days'],
            'currency': self._currency_payload(currency),
            'grand_total': grand_total,
            'grand_total_str': formatLang(
                self.env, grand_total, currency_obj=currency),
            'buckets': buckets,
            'can_notify': self.env.user.has_group(
                'gn_customer_due_alerts.group_customer_due_alert_manager'),
        }

    @api.model
    def get_due_traffic_dashboard_data(self):
        """Tablero 1: semaforo de vencimientos por factura."""
        self._check_user_access()
        company = self.env.company
        today = fields.Date.context_today(self)
        currency = company.currency_id
        invoices = self._open_invoices(company)
        receivable_lines = self._open_receivable_lines(company)

        kpis = {k: {'count': 0, 'total': 0.0} for k in self.DUE_TRAFFIC_ORDER}
        lines = []
        overdue_total = 0.0
        due_7_total = 0.0

        def _append_line(partner_id, partner_name, name, invoice_date, date_due,
                         days, residual, bucket, source, record_id, move_id):
            nonlocal overdue_total, due_7_total
            kpis[bucket]['count'] += 1
            kpis[bucket]['total'] += residual
            if days < 0:
                overdue_total += residual
            if 1 <= days <= 7:
                due_7_total += residual
            lines.append({
                'id': record_id,
                'source': source,
                'move_id': move_id,
                'partner_id': partner_id,
                'partner': partner_name,
                'name': name,
                'invoice_date': invoice_date,
                'date_due': date_due,
                'days': days,
                'residual': residual,
                'residual_str': self._fmt(residual, currency),
                'bucket': bucket,
                'status': self.DUE_TRAFFIC_LABELS[bucket],
            })

        for m in invoices:
            days = (m.invoice_date_due - today).days
            bucket = self._due_traffic_bucket(days)
            residual = self._residual(m)
            _append_line(
                m.partner_id.id, m.partner_id.display_name or '',
                self._customer_invoice_ref(m),
                self._fmt_date(m.invoice_date),
                self._fmt_date(m.invoice_date_due),
                days, residual, bucket, 'invoice', m.id, m.id)

        for line in receivable_lines:
            ref_date = self._line_ref_date(line)
            days = (ref_date - today).days
            bucket = self._due_traffic_bucket(days)
            residual = self._line_residual(line)
            _append_line(
                line.partner_id.id, line.partner_id.display_name or '',
                self._receivable_line_ref(line),
                self._fmt_date(line.move_id.date),
                self._fmt_date(ref_date),
                days, residual, bucket, 'receivable_line', line.id,
                line.move_id.id)

        grand_count = len(lines)
        grand_total = sum(k['total'] for k in kpis.values())
        overdue_pct = (overdue_total / grand_total * 100) if grand_total else 0.0

        cards = {}
        for key in self.DUE_TRAFFIC_ORDER:
            cards[key] = {
                'label': self.DUE_TRAFFIC_LABELS[key],
                'count': kpis[key]['count'],
                'total': kpis[key]['total'],
                'total_str': self._fmt(kpis[key]['total'], currency),
            }
        cards['total'] = {
            'label': 'Total general',
            'count': grand_count,
            'total': grand_total,
            'total_str': self._fmt(grand_total, currency),
        }

        due_today = self._due_today_summary(invoices, today, currency)

        return {
            'company': company.name,
            'today': self._fmt_date(today),
            'currency': self._currency_payload(currency),
            'cards': cards,
            'lines': lines,
            'due_today': due_today,
            'footer': {
                'overdue_total': overdue_total,
                'overdue_total_str': self._fmt(overdue_total, currency),
                'due_7_total': due_7_total,
                'due_7_total_str': self._fmt(due_7_total, currency),
                'overdue_pct': round(overdue_pct, 2),
            },
            'distribution': [
                {'key': k, 'pct': round(
                    kpis[k]['total'] / grand_total * 100, 1) if grand_total else 0}
                for k in self.DUE_TRAFFIC_ORDER
            ],
        }

    @api.model
    def get_aging_dashboard_data(self):
        """Tablero 2: antiguedad de CxC agrupada por cliente."""
        self._check_user_access()
        company = self.env.company
        today = fields.Date.context_today(self)
        currency = company.currency_id
        invoices = self._open_invoices(company)
        receivable_lines = self._open_receivable_lines(company)

        kpis = {k: {'count': 0, 'partners': set(), 'total': 0.0}
                for k in self.AGING_ORDER}
        partners = {}

        def _add_aging_item(partner, ref_date, residual):
            age = self._aging_days(ref_date, today)
            bucket = self._aging_bucket(age)
            pid = partner.id
            kpis[bucket]['count'] += 1
            kpis[bucket]['total'] += residual
            kpis[bucket]['partners'].add(pid)

            if pid not in partners:
                partners[pid] = {
                    'id': pid,
                    'name': partner.display_name or '',
                    'invoice_count': 0,
                    'total': 0.0,
                    'b0_30': 0.0, 'b31_60': 0.0,
                    'b61_90': 0.0, 'b90_plus': 0.0,
                    'max_age': 0,
                    'worst': 'b0_30',
                }
            p = partners[pid]
            p['invoice_count'] += 1
            p['total'] += residual
            p[bucket] += residual
            if age > p['max_age']:
                p['max_age'] = age
            if self.AGING_RANK[bucket] > self.AGING_RANK[p['worst']]:
                p['worst'] = bucket

        for m in invoices:
            _add_aging_item(m.partner_id, m.invoice_date_due, self._residual(m))

        for line in receivable_lines:
            _add_aging_item(
                line.partner_id, self._line_ref_date(line),
                self._line_residual(line))

        grand_total = sum(k['total'] for k in kpis.values())
        partner_count = len(partners)

        # KPI cards
        cards = {}
        for key in self.AGING_ORDER:
            cards[key] = {
                'label': self.AGING_LABELS[key],
                'short': self.AGING_STATUS[key],
                'range': self.AGING_RANGES[key],
                'partner_count': len(kpis[key]['partners']),
                'invoice_count': kpis[key]['count'],
                'total': kpis[key]['total'],
                'total_str': self._fmt(kpis[key]['total'], currency),
                'pct': round(
                    kpis[key]['total'] / grand_total * 100, 0) if grand_total else 0,
            }

        # Resumen secundario
        oldest = max(partners.values(), key=lambda x: x['max_age'], default=None)
        due_7_total = sum(
            self._residual(m) for m in invoices
            if 0 < (m.invoice_date_due - today).days <= 7)
        due_7_count = sum(
            1 for m in invoices
            if 0 < (m.invoice_date_due - today).days <= 7)

        partner_rows = []
        for p in sorted(partners.values(), key=lambda x: (-x['total'], x['name'])):
            partner_rows.append({
                'id': p['id'],
                'name': p['name'],
                'invoice_count': p['invoice_count'],
                'total': p['total'],
                'total_str': self._fmt(p['total'], currency),
                'b0_30': p['b0_30'],
                'b0_30_str': self._fmt(p['b0_30'], currency) if p['b0_30'] else '-',
                'b31_60': p['b31_60'],
                'b31_60_str': self._fmt(p['b31_60'], currency) if p['b31_60'] else '-',
                'b61_90': p['b61_90'],
                'b61_90_str': self._fmt(p['b61_90'], currency) if p['b61_90'] else '-',
                'b90_plus': p['b90_plus'],
                'b90_plus_str': self._fmt(p['b90_plus'], currency) if p['b90_plus'] else '-',
                'max_age': p['max_age'],
                'status': self.AGING_STATUS[p['worst']],
                'worst': p['worst'],
            })

        return {
            'company': company.name,
            'today': self._fmt_date(today),
            'currency': self._currency_payload(currency),
            'cards': cards,
            'summary': {
                'grand_total': grand_total,
                'grand_total_str': self._fmt(grand_total, currency),
                'partner_count': partner_count,
                'oldest_days': oldest['max_age'] if oldest else 0,
                'oldest_partner': oldest['name'] if oldest else '',
                'due_7_total': due_7_total,
                'due_7_total_str': self._fmt(due_7_total, currency),
                'due_7_count': due_7_count,
            },
            'distribution': [
                {'key': k, 'pct': cards[k]['pct'], 'label': self.AGING_LABELS[k]}
                for k in self.AGING_ORDER
            ],
            'partners': partner_rows,
        }

    # ------------------------------------------------------------------
    # Usuarios destinatarios
    # ------------------------------------------------------------------
    @api.model
    def _alert_users(self):
        group = self.env.ref(
            'gn_customer_due_alerts.group_customer_due_alert_user',
            raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        return group.users.filtered(lambda u: u.active)

    # ------------------------------------------------------------------
    # Notificaciones emergentes (bus) + correo
    # ------------------------------------------------------------------
    @api.model
    def _push_popup(self, user, title, message, sticky=True, warning=True):
        self.env['bus.bus']._sendone(
            user.partner_id,
            'simple_notification',
            {
                'title': title,
                'message': message,
                'sticky': sticky,
                'warning': warning,
            },
        )

    @api.model
    def _popup_message(self, info, company, invoices=None, today=None, currency=None):
        c = info['raw_counts']
        parts = []
        if company.customer_due_alert_include_overdue and c['overdue']:
            parts.append(_('%d vencidas') % c['overdue'])
        if invoices is not None and today is not None and currency is not None:
            due_today = self._due_today_summary(invoices, today, currency)
            if due_today['count']:
                parts.append(due_today['text'])
            elif c['today']:
                parts.append(_('%d vencen hoy') % c['today'])
        elif c['today']:
            parts.append(_('%d vencen hoy') % c['today'])
        if c['soon']:
            parts.append(_('%d proximas (<= %dd)') % (c['soon'], info['soon_days']))
        return '\n\n'.join(parts) if any(
            '\n' in p for p in parts) else ', '.join(parts)

    @api.model
    def _send_email(self, user, info, company, invoices=None):
        currency = info['currency']
        due_today = self._due_today_summary(
            invoices, info['today'], currency) if invoices else {
            'count': 0, 'total_str': '', 'text': '', 'items': []}
        values = {
            'company': company,
            'user': user,
            'today': self._fmt_date(info['today']),
            'soon_days': info['soon_days'],
            'include_overdue': company.customer_due_alert_include_overdue,
            'buckets': info['buckets'],
            'labels': BUCKET_LABELS,
            'order': BUCKET_ORDER,
            'due_today': due_today,
            'colors': {
                'overdue': '#c0392b',
                'today': '#e67e22',
                'soon': '#f1c40f',
                'upcoming': '#27ae60',
            },
            'totals': {
                k: formatLang(self.env, info['totals'][k], currency_obj=currency)
                for k in BUCKET_ORDER
            },
            'counts': info['raw_counts'],
        }
        body = self.env['ir.qweb']._render(
            'gn_customer_due_alerts.email_customer_due_summary', values)
        subject = _('Alertas de cobro - %s (%s)') % (
            company.name, self._fmt_date(info['today']))
        # SUDO-JUSTIFIED: cron envia correo transaccional sin sesion de usuario destino.
        mail = self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body,
            'email_to': user.email,
            'auto_delete': True,
        })
        mail.send()

    @api.model
    def _run_notifications(self, manual=False, popup=True, email=True):
        """Ejecuta el envio de alertas para todas las companias."""
        total_users = 0
        for company in self.env['res.company'].search([]):
            if not manual and not company.customer_due_alert_enabled:
                continue
            svc = self.with_company(company)
            info = svc._collect(company)
            invoices = svc._open_invoices(company)
            c = info['raw_counts']
            relevant = c['today'] + c['soon'] + (
                c['overdue'] if company.customer_due_alert_include_overdue else 0)
            if not relevant:
                continue
            users = svc._alert_users()
            title = _('Facturas de cliente por cobrar')
            message = svc._popup_message(
                info, company, invoices=invoices,
                today=info['today'], currency=info['currency'])
            for user in users:
                if popup and user.partner_id:
                    svc._push_popup(
                        user, title, message,
                        sticky=company.customer_due_alert_popup_sticky)
                if email and user.email:
                    svc._send_email(user, info, company, invoices=invoices)
                total_users += 1
        return total_users

    @api.model
    def _cron_notify_due_invoices(self):
        self._run_notifications(manual=False)
        return True

    @api.model
    def action_send_alerts_now(self):
        if not self.env.user.has_group(
                'gn_customer_due_alerts.group_customer_due_alert_manager'):
            raise AccessError(_(
                'Solo un administrador de alertas puede enviarlas manualmente.'))
        n = self._run_notifications(manual=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Alertas enviadas'),
                'message': _('Se notifico a %d usuario(s) con permiso.') % n,
                'type': 'success',
                'sticky': False,
            },
        }
