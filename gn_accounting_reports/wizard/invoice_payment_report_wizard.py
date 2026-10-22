# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class GnAccountingInvoicePaymentReportWizard(models.TransientModel):
    _name = 'gn.accounting.invoice.payment.report.wizard'
    _description = 'Reporte premium facturas y pagos'

    date_from = fields.Date(
        string='Fecha pago desde',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string='Fecha pago hasta',
        required=True,
        default=fields.Date.context_today,
    )
    invoice_date_from = fields.Date(string='Fecha factura desde')
    invoice_date_to = fields.Date(string='Fecha factura hasta')
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    branch_ids = fields.Many2many('res.branch', string='Sucursales')
    user_ids = fields.Many2many(
        'res.users',
        'gn_inv_pay_report_wizard_user_rel',
        'wizard_id',
        'user_id',
        string='Asesores / vendedores',
    )
    partner_ids = fields.Many2many('res.partner', string='Clientes')
    journal_ids = fields.Many2many(
        'account.journal',
        'gn_inv_pay_report_wizard_journal_rel',
        'wizard_id',
        'journal_id',
        string='Bancos / diarios',
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
    )
    categ_ids = fields.Many2many(
        'product.category',
        'gn_inv_pay_report_wizard_categ_rel',
        'wizard_id',
        'categ_id',
        string='Categorías de producto',
    )
    payment_state = fields.Selection(
        [
            ('all', 'Todos'),
            ('paid', 'Pagadas'),
            ('partial', 'Parcialmente pagadas'),
            ('not_paid', 'Pendientes de pago'),
        ],
        string='Estado de factura',
        default='all',
        required=True,
    )
    credit_term_filter = fields.Selection(
        [
            ('all', 'Todos'),
            ('within', 'Pagadas dentro del plazo'),
            ('outside', 'Pagadas fuera del plazo'),
            ('no_payment', 'Sin pago en el período'),
        ],
        string='Plazo de crédito',
        default='all',
        required=True,
    )
    show_pending_invoices = fields.Boolean(
        string='Incluir facturas pendientes sin pago',
        default=True,
        help='Muestra facturas publicadas en el rango de fechas de factura que no '
             'tienen pago registrado en el período seleccionado.',
    )

    @api.constrains('date_from', 'date_to', 'invoice_date_from', 'invoice_date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                raise UserError(_('La fecha inicial de pago no puede ser posterior a la final.'))
            if (
                wiz.invoice_date_from
                and wiz.invoice_date_to
                and wiz.invoice_date_from > wiz.invoice_date_to
            ):
                raise UserError(_('La fecha inicial de factura no puede ser posterior a la final.'))

    def _fmt_date(self, value):
        if not value:
            return ''
        if isinstance(value, str):
            value = fields.Date.from_string(value)
        return value.strftime('%d/%m/%Y')

    def _fmt_qty(self, val):
        if val in ('', None):
            return ''
        return formatLang(self.env, val, digits=2)

    def _fmt_money(self, val):
        if val in ('', None):
            return ''
        return formatLang(
            self.env,
            val,
            digits=2,
            currency_obj=self.company_id.currency_id,
        )

    def _payment_state_label(self, invoice):
        labels = {
            'not_paid': _('Pendiente'),
            'in_payment': _('En proceso de pago'),
            'paid': _('Pagada'),
            'partial': _('Parcial'),
            'reversed': _('Revertida'),
            'invoicing_legacy': _('Legacy'),
        }
        return labels.get(invoice.payment_state, invoice.payment_state or '')

    def _partner_credit_granted(self, partner):
        if hasattr(partner, 'credit_check') and partner.credit_check:
            if hasattr(partner, 'credit_blocking'):
                return partner.credit_blocking or 0.0
        return getattr(partner, 'credit_limit', 0.0) or 0.0

    def _partner_rank_label(self, partner):
        rank = partner.customer_rank or 0
        if not rank:
            return _('Sin ranking')
        return _('Ranking %s') % rank

    def _invoice_due_date(self, invoice):
        if invoice.invoice_date_due:
            return invoice.invoice_date_due
        return invoice.invoice_date

    def _invoice_categories(self, invoice):
        categories = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id
        ).mapped('product_id.categ_id.complete_name')
        return ', '.join(sorted(set(filter(None, categories))))

    def _get_categ_child_ids(self):
        if not self.categ_ids:
            return None
        return set(self.env['product.category'].search([
            ('id', 'child_of', self.categ_ids.ids),
        ]).ids)

    def _invoice_matches_category_filter(self, invoice, categ_child_ids=None):
        if categ_child_ids is None:
            categ_child_ids = self._get_categ_child_ids()
        if not categ_child_ids:
            return True
        line_categs = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id
        ).mapped('product_id.categ_id.id')
        return bool(set(line_categs) & categ_child_ids)

    def _base_invoice_domain(self, extra=None):
        self.ensure_one()
        domain = [
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        if self.branch_ids and 'branch_id' in self.env['account.move']._fields:
            domain.append(('branch_id', 'in', self.branch_ids.ids))
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        if self.invoice_date_from:
            domain.append(('invoice_date', '>=', self.invoice_date_from))
        if self.invoice_date_to:
            domain.append(('invoice_date', '<=', self.invoice_date_to))
        if self.payment_state != 'all':
            domain.append(('payment_state', '=', self.payment_state))
        if self.user_ids:
            domain.append(('invoice_user_id', 'in', self.user_ids.ids))
        if extra:
            domain.extend(extra)
        return domain

    def _prefetch_invoices(self, invoices):
        if not invoices:
            return
        invoices.read([
            'name', 'invoice_date', 'invoice_date_due', 'partner_id', 'invoice_user_id',
            'amount_untaxed', 'amount_tax', 'amount_total', 'payment_state', 'move_type',
            'branch_id', 'invoice_line_ids', 'company_id', 'state',
        ])
        invoices.mapped('partner_id')
        invoices.mapped('invoice_user_id')
        invoices.mapped('invoice_line_ids.product_id.categ_id')
        if 'branch_id' in self.env['account.move']._fields:
            invoices.mapped('branch_id')

    def _build_invoice_meta(self, invoices, categ_child_ids):
        meta = {}
        for inv in invoices:
            product_lines = inv.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.product_id
            )
            line_categs = product_lines.mapped('product_id.categ_id')
            if categ_child_ids is not None:
                if not (set(line_categs.ids) & categ_child_ids):
                    meta[inv.id] = {'skip': True}
                    continue
            categories = ', '.join(sorted(set(filter(None, line_categs.mapped('complete_name')))))
            advisor = inv.invoice_user_id.name if inv.invoice_user_id else ''
            if not advisor:
                sale_orders = product_lines.mapped('sale_line_ids.order_id')
                if sale_orders:
                    advisor = sale_orders[0].user_id.name or ''
            partner = inv.partner_id
            meta[inv.id] = {
                'skip': False,
                'advisor': advisor,
                'categories': categories,
                'credit_granted': self._partner_credit_granted(partner),
                'customer_rank': self._partner_rank_label(partner),
                'branch': inv.branch_id.name if getattr(inv, 'branch_id', False) else '',
            }
        return meta

    def _advisor_name(self, invoice):
        if invoice.invoice_user_id:
            return invoice.invoice_user_id.name
        sale_orders = invoice.invoice_line_ids.mapped('sale_line_ids.order_id')
        if sale_orders:
            return sale_orders[0].user_id.name or ''
        return ''

    def _invoice_passes_filters(self, invoice, advisor_user_id=None, categ_child_ids=None):
        self.ensure_one()
        if invoice.move_type not in ('out_invoice', 'out_refund'):
            return False
        if invoice.state != 'posted':
            return False
        if invoice.company_id != self.company_id:
            return False
        if self.branch_ids and getattr(invoice, 'branch_id', False):
            if invoice.branch_id not in self.branch_ids:
                return False
        elif self.branch_ids:
            return False
        if self.partner_ids and invoice.partner_id not in self.partner_ids:
            return False
        if self.invoice_date_from and invoice.invoice_date:
            if invoice.invoice_date < self.invoice_date_from:
                return False
        if self.invoice_date_to and invoice.invoice_date:
            if invoice.invoice_date > self.invoice_date_to:
                return False
        if self.payment_state != 'all' and invoice.payment_state != self.payment_state:
            return False
        if not self._invoice_matches_category_filter(invoice, categ_child_ids):
            return False
        if self.user_ids:
            advisor = advisor_user_id or (
                invoice.invoice_user_id.id if invoice.invoice_user_id else False
            )
            if not advisor:
                sale_orders = invoice.invoice_line_ids.mapped('sale_line_ids.order_id')
                advisor = sale_orders[:1].user_id.id if sale_orders else False
            if advisor not in self.user_ids.ids:
                return False
        return True

    def _payment_domain(self):
        self.ensure_one()
        domain = [
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
            ('company_id', '=', self.company_id.id),
            ('state', 'not in', ('draft', 'canceled', 'rejected')),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        if self.branch_ids and 'branch_id' in self.env['account.payment']._fields:
            domain.append(('branch_id', 'in', self.branch_ids.ids))
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        return domain

    def _append_row(self, rows, seen, invoice, payment, amount_applied, payment_date, meta=None):
        inv_meta = (meta or {}).get(invoice.id, {})
        if inv_meta.get('skip'):
            return

        key = (invoice.id, payment.id if payment else 0, amount_applied)
        if key in seen:
            return
        seen.add(key)

        inv_date = invoice.invoice_date
        pay_date = payment_date
        due_date = self._invoice_due_date(invoice)
        today = fields.Date.context_today(self)
        days_invoice_to_payment = ''
        within_credit = ''
        days_overdue = 0
        is_overdue = False
        if inv_date and pay_date:
            days_invoice_to_payment = (pay_date - inv_date).days
            if due_date and pay_date:
                within_credit = _('Sí') if pay_date <= due_date else _('No')
        if due_date and invoice.payment_state in ('not_paid', 'partial', 'in_payment'):
            if today > due_date:
                days_overdue = (today - due_date).days
                is_overdue = True

        amount_untaxed = abs(invoice.amount_untaxed)
        amount_tax = abs(invoice.amount_tax)
        amount_total = abs(invoice.amount_total)
        applied = abs(amount_applied or 0.0)
        if invoice.move_type == 'out_refund':
            applied = -applied
        balance_pending = max(0.0, amount_total - applied) if payment else (
            amount_total if invoice.payment_state != 'paid' else 0.0
        )
        credit_term_days = ''
        if inv_date and due_date:
            credit_term_days = (due_date - inv_date).days

        rows.append({
            'invoice_id': invoice.id,
            'payment_id': payment.id if payment else False,
            'partner_id': invoice.partner_id.id,
            'user_id': invoice.invoice_user_id.id if invoice.invoice_user_id else False,
            'journal_id': payment.journal_id.id if payment and payment.journal_id else False,
            'branch_id': invoice.branch_id.id if getattr(invoice, 'branch_id', False) else False,
            'customer': invoice.partner_id.display_name or '',
            'invoice_number': invoice.name or '',
            'invoice_date': self._fmt_date(inv_date),
            'invoice_date_raw': fields.Date.to_string(inv_date) if inv_date else False,
            'due_date': self._fmt_date(due_date) if due_date else '',
            'due_date_raw': fields.Date.to_string(due_date) if due_date else False,
            'payment_receipt': payment.name if payment else '',
            'payment_date': self._fmt_date(pay_date) if pay_date else '',
            'payment_date_raw': fields.Date.to_string(pay_date) if pay_date else False,
            'days_invoice_to_payment': days_invoice_to_payment if days_invoice_to_payment != '' else '',
            'days_diff': days_invoice_to_payment if days_invoice_to_payment != '' else '',
            'days_overdue': days_overdue,
            'is_overdue': is_overdue,
            'credit_term_days': credit_term_days if credit_term_days != '' else '',
            'advisor': inv_meta.get('advisor') or self._advisor_name(invoice),
            'bank': payment.journal_id.display_name if payment and payment.journal_id else '',
            'amount_untaxed': amount_untaxed,
            'amount_tax': amount_tax,
            'amount_total': amount_total,
            'amount_applied': abs(applied),
            'balance_pending': balance_pending,
            'invoice_status': self._payment_state_label(invoice),
            'payment_state': invoice.payment_state or '',
            'payment_user': payment.create_uid.name if payment and payment.create_uid else '',
            'payment_user_id': payment.create_uid.id if payment and payment.create_uid else False,
            'credit_granted': inv_meta.get(
                'credit_granted', self._partner_credit_granted(invoice.partner_id)
            ),
            'within_credit': within_credit,
            'customer_rank': inv_meta.get(
                'customer_rank', self._partner_rank_label(invoice.partner_id)
            ),
            'customer_rank_num': invoice.partner_id.customer_rank or 0,
            'payment_method': (
                payment.payment_method_line_id.name
                if payment and hasattr(payment, 'payment_method_line_id') and payment.payment_method_line_id
                else (payment.payment_method_id.name if payment and payment.payment_method_id else '')
            ),
            'bank_reference': (
                payment.payment_reference or payment.memo or ''
                if payment else ''
            ),
            'product_categories': inv_meta.get(
                'categories', self._invoice_categories(invoice)
            ),
            'branch': inv_meta.get(
                'branch',
                invoice.branch_id.name if getattr(invoice, 'branch_id', False) else '',
            ),
            'currency_id': invoice.currency_id.id,
            'currency_symbol': invoice.currency_id.symbol or '',
            '_sort_payment_date': pay_date or fields.Date.from_string('1900-01-01'),
            '_sort_invoice_date': inv_date or fields.Date.from_string('1900-01-01'),
            '_within_credit_bool': within_credit == _('Sí'),
            '_has_payment': bool(payment),
        })

    def _invoice_passes_filters_fast(self, invoice, meta, categ_child_ids=None):
        if meta.get(invoice.id, {}).get('skip'):
            return False
        return self._invoice_passes_filters(invoice, categ_child_ids=categ_child_ids)

    def _collect_from_payment_lines(self, rows, seen, payments, categ_child_ids):
        if 'invoice_lines' not in self.env['account.payment']._fields:
            return self.env['account.payment']
        line_domain = [('payment_id', 'in', payments.ids)]
        if self.user_ids:
            line_domain.append(('invoice_id.invoice_user_id', 'in', self.user_ids.ids))
        lines = self.env['payment.invoice.line'].search(line_domain)
        if not lines:
            return self.env['account.payment']
        invoices = lines.mapped('invoice_id')
        self._prefetch_invoices(invoices)
        invoice_meta = self._build_invoice_meta(invoices, categ_child_ids)
        payments_with_lines = self.env['account.payment']
        for line in lines:
            invoice = line.invoice_id
            payment = line.payment_id
            if not invoice or not payment:
                continue
            if not self._invoice_passes_filters_fast(invoice, invoice_meta, categ_child_ids):
                continue
            amount = line.amount or line.actual_amount or 0.0
            self._append_row(
                rows, seen, invoice, payment, amount, payment.date, invoice_meta
            )
            payments_with_lines |= payment
        return payments_with_lines

    def _collect_from_reconciled(self, rows, seen, payments, payments_with_lines, categ_child_ids):
        remaining = payments - payments_with_lines
        if not remaining:
            return
        remaining.read(['reconciled_invoice_ids', 'journal_id', 'create_uid', 'name', 'date', 'amount'])
        for payment in remaining:
            invoices = payment.reconciled_invoice_ids.filtered(
                lambda m: m.move_type in ('out_invoice', 'out_refund') and m.state == 'posted'
            )
            if self.user_ids:
                invoices = invoices.filtered(
                    lambda m: m.invoice_user_id.id in self.user_ids.ids
                )
            if not invoices:
                continue
            self._prefetch_invoices(invoices)
            invoice_meta = self._build_invoice_meta(invoices, categ_child_ids)
            for invoice in invoices:
                if not self._invoice_passes_filters_fast(invoice, invoice_meta, categ_child_ids):
                    continue
                widget = invoice.invoice_payments_widget or {}
                applied = 0.0
                for item in widget.get('content', []):
                    if item.get('account_payment_id') == payment.id:
                        applied = item.get('amount', 0.0)
                        break
                if not applied:
                    applied = payment.amount
                self._append_row(
                    rows, seen, invoice, payment, applied, payment.date, invoice_meta
                )

    def _collect_pending_invoices(self, rows, seen, categ_child_ids):
        if not self.show_pending_invoices:
            return
        inv_from = self.invoice_date_from or self.date_from
        inv_to = self.invoice_date_to or self.date_to
        domain = self._base_invoice_domain([
            ('payment_state', 'in', ('not_paid', 'partial', 'in_payment')),
            ('invoice_date', '>=', inv_from),
            ('invoice_date', '<=', inv_to),
        ])
        invoices = self.env['account.move'].search(domain)
        self._prefetch_invoices(invoices)
        invoice_meta = self._build_invoice_meta(invoices, categ_child_ids)
        for invoice in invoices:
            if not self._invoice_passes_filters_fast(invoice, invoice_meta, categ_child_ids):
                continue
            key = (invoice.id, 0, 0.0)
            if key in seen:
                continue
            self._append_row(rows, seen, invoice, False, 0.0, False, invoice_meta)

    def _apply_credit_term_filter(self, rows):
        if self.credit_term_filter == 'all':
            return rows
        filtered = []
        for row in rows:
            if self.credit_term_filter == 'no_payment':
                if not row['_has_payment']:
                    filtered.append(row)
            elif self.credit_term_filter == 'within':
                if row['_has_payment'] and row['_within_credit_bool']:
                    filtered.append(row)
            elif self.credit_term_filter == 'outside':
                if row['_has_payment'] and row.get('within_credit') == _('No'):
                    filtered.append(row)
        return filtered

    def _build_report_data(self):
        self.ensure_one()
        payments = self.env['account.payment'].search(self._payment_domain())
        rows = []
        seen = set()
        categ_child_ids = self._get_categ_child_ids()

        payments_with_lines = self._collect_from_payment_lines(
            rows, seen, payments, categ_child_ids
        )
        self._collect_from_reconciled(
            rows, seen, payments, payments_with_lines, categ_child_ids
        )
        self._collect_pending_invoices(rows, seen, categ_child_ids)

        rows = self._apply_credit_term_filter(rows)
        rows.sort(
            key=lambda r: (
                r['_sort_payment_date'],
                r['_sort_invoice_date'],
                r['invoice_number'],
            ),
            reverse=True,
        )

        totals = {
            'amount_untaxed': sum(r['amount_untaxed'] for r in rows),
            'amount_tax': sum(r['amount_tax'] for r in rows),
            'amount_total': sum(r['amount_total'] for r in rows),
            'amount_applied': sum(r['amount_applied'] for r in rows),
        }

        if self.branch_ids:
            branch_label = ', '.join(self.branch_ids.mapped('name'))
        else:
            branch_label = _('Todas')
        if self.user_ids:
            user_label = ', '.join(self.user_ids.mapped('name'))
        else:
            user_label = _('Todos')
        if self.partner_ids:
            partner_label = ', '.join(self.partner_ids.mapped('name'))
        else:
            partner_label = _('Todos')
        if self.journal_ids:
            journal_label = ', '.join(self.journal_ids.mapped('display_name'))
        else:
            journal_label = _('Todos')
        if self.categ_ids:
            categ_label = ', '.join(self.categ_ids.mapped('complete_name'))
        else:
            categ_label = _('Todas')

        return {
            'rows': rows,
            'totals': totals,
            'branch_label': branch_label,
            'user_label': user_label,
            'partner_label': partner_label,
            'journal_label': journal_label,
            'categ_label': categ_label,
            'payment_state_label': dict(
                self._fields['payment_state'].selection
            ).get(self.payment_state, ''),
            'credit_term_label': dict(
                self._fields['credit_term_filter'].selection
            ).get(self.credit_term_filter, ''),
        }

    def action_print_pdf(self):
        self.ensure_one()
        report = self.env.ref(
            'gn_accounting_reports.action_report_gn_invoice_payment',
            raise_if_not_found=True,
        )
        return report.report_action(self)

    def action_export_html_browser(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/html/gn_accounting_reports.report_invoice_payment_html/%s' % self.id,
            'target': 'new',
        }
