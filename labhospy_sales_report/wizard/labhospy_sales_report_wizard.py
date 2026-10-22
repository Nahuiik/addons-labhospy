# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_MONTH_NAMES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


class LabhospySalesReportWizard(models.TransientModel):
    _name = 'labhospy.sales.report.wizard'
    _description = 'Wizard reporte de ventas LabHosPy'

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
        help='Muestra columnas de valor libre de impuesto por período y totales.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                raise UserError(_('La fecha inicial no puede ser posterior a la final.'))

    def _line_period_key(self, order_datetime):
        """Clave de bucket coherente con `_iter_period_slots`."""
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
        """Períodos calendario entre date_from y date_to (columnas y divisor del promedio)."""
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

    def action_export_xlsx(self):
        self.ensure_one()
        return self.env.ref(
            'labhospy_sales_report.action_report_labhospy_sales_xlsx'
        ).report_action(self)
