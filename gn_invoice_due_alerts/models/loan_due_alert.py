# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools.misc import formatLang, format_date

LOAN_BUCKET_LABELS = {
    'paid': 'Pagado este mes',
    'today': 'Vence hoy',
    'due_1_7': 'Por vencer (1-7 dias)',
    'due_8_15': 'Por vencer (8-15 dias)',
    'overdue': 'Vencida',
    'al_dia': 'Al dia',
}
LOAN_BUCKET_ORDER = ['overdue', 'today', 'due_1_7', 'due_8_15', 'al_dia', 'paid']


class LoanDueAlert(models.AbstractModel):
    _name = 'gn.loan.due.alert'
    _description = 'Servicio de alertas de vencimiento de prestamos'

    @api.model
    def _check_user_access(self):
        if not self.env.user.has_group(
                'gn_invoice_due_alerts.group_invoice_due_alert_user'):
            raise AccessError(_(
                'No tiene permiso para ver las alertas de vencimiento.'))

    @api.model
    def _fmt(self, amount, currency):
        return formatLang(self.env, amount, currency_obj=currency)

    @api.model
    def _fmt_date(self, value):
        if not value:
            return ''
        return format_date(self.env, value, date_format='dd/MM/yyyy')

    @api.model
    def _currency_payload(self, currency):
        return {
            'symbol': currency.symbol or '',
            'position': currency.position or 'before',
            'digits': currency.decimal_places,
        }

    @api.model
    def _due_today_summary(self, loans, today, currency):
        items = []
        for loan in loans:
            if loan.due_bucket != 'today' or loan.paid_current_month:
                continue
            items.append({
                'bank': loan.bank or '',
                'loan_number': loan.loan_number or '',
                'amount': loan.monthly_fee,
                'amount_str': self._fmt(loan.monthly_fee, currency),
            })
        count = len(items)
        total = sum(i['amount'] for i in items)
        total_str = self._fmt(total, currency)
        if not count:
            text = _('Hoy no hay cuotas de prestamos que venzan.')
        else:
            header = _(
                'Hoy vencen %(count)d cuota(s) de prestamo por un total de %(total)s:'
            ) % {'count': count, 'total': total_str}
            detail = '\n'.join(
                _('• %(bank)s — %(loan)s — %(amount)s') % {
                    'bank': it['bank'],
                    'loan': it['loan_number'],
                    'amount': it['amount_str'],
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

    @api.model
    def get_loan_dashboard_data(self):
        self._check_user_access()
        company = self.env.company
        today = fields.Date.context_today(self)
        currency = company.currency_id
        Loan = self.env['gn.bank.loan']
        loans = Loan.search([
            ('company_id', '=', company.id),
            ('state', '=', 'active'),
        ], order='bank, loan_number')

        kpis = {k: {'count': 0, 'total': 0.0} for k in LOAN_BUCKET_ORDER}
        lines = []
        banks = {}

        for loan in loans:
            bucket = loan.due_bucket or 'al_dia'
            fee = loan.monthly_fee or 0.0
            kpis[bucket]['count'] += 1
            kpis[bucket]['total'] += fee
            bank_key = loan.bank or _('Sin banco')
            if bank_key not in banks:
                banks[bank_key] = {
                    'name': bank_key,
                    'count': 0,
                    'total_fee': 0.0,
                    'balance': 0.0,
                }
            banks[bank_key]['count'] += 1
            banks[bank_key]['total_fee'] += fee
            banks[bank_key]['balance'] += loan.balance or 0.0
            lines.append({
                'id': loan.id,
                'bank': loan.bank or '',
                'loan_number': loan.loan_number or '',
                'purpose': loan.purpose or '',
                'monthly_fee': fee,
                'monthly_fee_str': self._fmt(fee, currency),
                'balance': loan.balance or 0.0,
                'balance_str': self._fmt(loan.balance or 0.0, currency),
                'payment_day': loan.payment_day,
                'next_due_date': self._fmt_date(loan.next_due_date),
                'days': loan.days_to_due,
                'rate': loan.rate,
                'end_date': self._fmt_date(loan.end_date),
                'bucket': bucket,
                'status': LOAN_BUCKET_LABELS.get(bucket, bucket),
                'paid_current_month': loan.paid_current_month,
                'debit_count': loan.debit_count,
            })

        grand_count = len(lines)
        grand_fee = sum(l['monthly_fee'] for l in lines)
        grand_balance = sum(l['balance'] for l in lines)
        overdue_total = kpis['overdue']['total']

        cards = {}
        for key in LOAN_BUCKET_ORDER:
            cards[key] = {
                'label': LOAN_BUCKET_LABELS[key],
                'count': kpis[key]['count'],
                'total': kpis[key]['total'],
                'total_str': self._fmt(kpis[key]['total'], currency),
            }
        cards['total'] = {
            'label': 'Total general',
            'count': grand_count,
            'total': grand_fee,
            'total_str': self._fmt(grand_fee, currency),
        }

        due_today = self._due_today_summary(loans, today, currency)
        bank_rows = sorted(banks.values(), key=lambda b: (-b['total_fee'], b['name']))
        for b in bank_rows:
            b['total_fee_str'] = self._fmt(b['total_fee'], currency)
            b['balance_str'] = self._fmt(b['balance'], currency)

        return {
            'company': company.name,
            'today': self._fmt_date(today),
            'currency': self._currency_payload(currency),
            'can_manage': self.env.user.has_group(
                'gn_invoice_due_alerts.group_invoice_due_alert_manager'),
            'cards': cards,
            'lines': lines,
            'banks': bank_rows,
            'due_today': due_today,
            'footer': {
                'grand_fee': grand_fee,
                'grand_fee_str': self._fmt(grand_fee, currency),
                'grand_balance': grand_balance,
                'grand_balance_str': self._fmt(grand_balance, currency),
                'overdue_total': overdue_total,
                'overdue_total_str': self._fmt(overdue_total, currency),
                'overdue_count': kpis['overdue']['count'],
            },
        }
