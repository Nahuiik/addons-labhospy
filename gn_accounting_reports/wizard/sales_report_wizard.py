# -*- coding: utf-8 -*-

from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

_MONTH_NAMES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


class GnAccountingSalesReportWizard(models.TransientModel):
    _name = 'gn.accounting.sales.report.wizard'
    _description = 'Reporte de ventas por período'

    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    group_by = fields.Selection(
        [
            ('month', 'Mensual'),
            ('quarter', 'Trimestral'),
            ('year', 'Anual'),
        ],
        string='Agrupar por',
        default='month',
        required=True,
    )
    include_untaxed_value = fields.Boolean(
        string='Incluir valor sin impuestos',
        default=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    branch_ids = fields.Many2many(
        'res.branch',
        string='Sucursales',
        help='Vacío = todas las sucursales de la compañía.',
    )
    user_ids = fields.Many2many(
        'res.users',
        'gn_accounting_sales_report_wizard_user_rel',
        'wizard_id',
        'user_id',
        string='Vendedores',
        help='Vacío = todos los vendedores.',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                raise UserError(_('La fecha inicial no puede ser posterior a la final.'))

    def _line_period_key(self, order_datetime):
        self.ensure_one()
        if not order_datetime:
            return None
        d = fields.Datetime.to_datetime(order_datetime).date()
        if self.group_by == 'month':
            return d.year, d.month
        if self.group_by == 'quarter':
            return d.year, (d.month - 1) // 3 + 1
        return (d.year,)

    def _period_label_for_key(self, key):
        self.ensure_one()
        if not key:
            return ''
        if self.group_by == 'month':
            y, m = key
            return f'{_MONTH_NAMES.get(m, m)} {y}'
        if self.group_by == 'quarter':
            y, q = key
            return _('Q%(q)s %(year)s') % {'q': q, 'year': y}
        return str(key[0])

    def _iter_period_slots(self):
        self.ensure_one()
        d0, d1 = self.date_from, self.date_to
        if self.group_by == 'month':
            cur = d0.replace(day=1)
            end = d1.replace(day=1)
            while cur <= end:
                key = (cur.year, cur.month)
                yield key, self._period_label_for_key(key)
                cur = cur + relativedelta(months=1)
        elif self.group_by == 'quarter':
            cur = d0.replace(day=1)
            end = d1.replace(day=1)
            seen = set()
            while cur <= end:
                qn = (cur.month - 1) // 3 + 1
                key = (cur.year, qn)
                if key not in seen:
                    seen.add(key)
                    yield key, self._period_label_for_key(key)
                cur = cur + relativedelta(months=1)
        else:
            for year in range(d0.year, d1.year + 1):
                key = (year,)
                yield key, str(year)

    def _sale_line_domain(self):
        self.ensure_one()
        date_from_dt = fields.Datetime.to_datetime(self.date_from)
        date_to_dt = fields.Datetime.to_datetime(self.date_to).replace(
            hour=23, minute=59, second=59,
        )
        domain = [
            ('order_id.state', 'in', ('sale', 'done')),
            ('order_id.date_order', '>=', date_from_dt),
            ('order_id.date_order', '<=', date_to_dt),
            ('display_type', '=', False),
            ('order_id.company_id', '=', self.company_id.id),
        ]
        if self.branch_ids:
            domain.append(('order_id.branch_id', 'in', self.branch_ids.ids))
        if self.user_ids:
            domain.append(('order_id.user_id', 'in', self.user_ids.ids))
        return domain

    def _product_extra_fields(self, tmpl):
        supplier = ''
        catalog = ''
        model = ''
        if hasattr(tmpl, 'gn_labhospy_supplier_id') and tmpl.gn_labhospy_supplier_id:
            supplier = tmpl.gn_labhospy_supplier_id.name or ''
        if hasattr(tmpl, 'gn_labhospy_catalog_code'):
            catalog = tmpl.gn_labhospy_catalog_code or ''
        if hasattr(tmpl, 'gn_labhospy_model'):
            model = tmpl.gn_labhospy_model or ''
        return supplier, catalog, model

    def _build_report_data(self):
        """Datos para QWEB / PDF."""
        self.ensure_one()
        period_list = list(self._iter_period_slots())
        period_keys = [p[0] for p in period_list]
        period_labels = [p[1] for p in period_list]
        period_key_set = set(period_keys)
        n_periods = max(len(period_keys), 1)

        SaleLine = self.env['sale.order.line'].sudo()
        lines = SaleLine.search(self._sale_line_domain())

        agg = {}
        product_ids = set()

        for line in lines:
            order = line.order_id
            pk = self._line_period_key(order.date_order)
            if pk not in period_key_set:
                continue
            uid = order.user_id.id if order.user_id else 0
            pid = order.partner_id.id if order.partner_id else 0
            pr = line.product_id
            if not pr:
                continue
            product_ids.add(pr.id)
            gkey = (pr.id, uid, pid)

            if gkey not in agg:
                tmpl = pr.product_tmpl_id
                supplier, catalog, model = self._product_extra_fields(tmpl)
                agg[gkey] = {
                    'supplier': supplier,
                    'code': pr.default_code or '',
                    'catalog': catalog,
                    'model': model,
                    'name': pr.display_name,
                    'categ': pr.categ_id.complete_name if pr.categ_id else '',
                    'user': order.user_id.name if order.user_id else '',
                    'partner': order.partner_id.name if order.partner_id else '',
                    'branch': order.branch_id.name if getattr(order, 'branch_id', False) else '',
                    'periods': defaultdict(lambda: {'qty': 0.0, 'untaxed': 0.0}),
                }
            cell = agg[gkey]['periods'][pk]
            cell['qty'] += line.product_uom_qty
            cell['untaxed'] += line.price_subtotal

        products = self.env['product.product'].sudo().browse(list(product_ids))
        qty_by_product = {p.id: p.qty_available for p in products}

        totals_qty_period = [0.0] * len(period_keys)
        totals_unt_period = [0.0] * len(period_keys)

        rows = []
        sorted_keys = sorted(
            agg.keys(),
            key=lambda k: (
                agg[k]['supplier'],
                agg[k]['code'],
                agg[k]['partner'],
                agg[k]['user'],
            ),
        )

        for gkey in sorted_keys:
            info = agg[gkey]
            pr_id = gkey[0]
            period_qty = []
            period_untaxed = []
            total_qty = 0.0
            total_untaxed = 0.0
            for i, pk in enumerate(period_keys):
                pdat = info['periods'].get(pk, {'qty': 0.0, 'untaxed': 0.0})
                q = pdat['qty']
                u = pdat['untaxed']
                period_qty.append(q)
                period_untaxed.append(u)
                total_qty += q
                total_untaxed += u
                totals_qty_period[i] += q
                totals_unt_period[i] += u

            rows.append({
                **{k: info[k] for k in (
                    'supplier', 'code', 'catalog', 'model', 'name',
                    'categ', 'user', 'partner', 'branch',
                )},
                'period_cells': [
                    {'qty': q, 'untaxed': u}
                    for q, u in zip(period_qty, period_untaxed)
                ],
                'total_qty': total_qty,
                'total_untaxed': total_untaxed,
                'avg_qty': total_qty / n_periods,
                'qty_on_hand': qty_by_product.get(pr_id, 0.0),
            })

        branches = self.branch_ids or self.env['res.branch'].search(
            [('company_id', '=', self.company_id.id)]
        )
        if self.branch_ids:
            branch_label = ', '.join(self.branch_ids.mapped('name'))
        else:
            branch_label = _('Todas')

        if self.user_ids:
            user_label = ', '.join(self.user_ids.mapped('name'))
        else:
            user_label = _('Todos')

        return {
            'periods': [{'key': k, 'label': lbl} for k, lbl in zip(period_keys, period_labels)],
            'include_untaxed': self.include_untaxed_value,
            'rows': rows,
            'totals_qty_period': totals_qty_period,
            'totals_unt_period': totals_unt_period,
            'period_totals': [
                {'qty': q, 'untaxed': u}
                for q, u in zip(totals_qty_period, totals_unt_period)
            ],
            'total_qty': sum(totals_qty_period),
            'total_untaxed': sum(totals_unt_period),
            'branch_label': branch_label,
            'user_label': user_label,
            'group_by_label': dict(self._fields['group_by'].selection).get(self.group_by, ''),
            'branches': branches,
        }

    def action_print_pdf(self):
        self.ensure_one()
        report = self.env.ref(
            'gn_accounting_reports.action_report_gn_sales',
            raise_if_not_found=True,
        )
        return report.report_action(self)

    def action_export_html_browser(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/html/gn_accounting_reports.report_sales_html/%s' % self.id,
            'target': 'new',
        }

    def _fmt_qty(self, val):
        if val in ('', None):
            return ''
        return formatLang(self.env, val, digits=2)

    def _fmt_money(self, val):
        if val in ('', None):
            return ''
        return formatLang(self.env, val, digits=2, monetary=True)
