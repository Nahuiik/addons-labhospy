# -*- coding: utf-8 -*-
import calendar
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class GnStockKardexWizard(models.TransientModel):
    _name = 'gn.stock.kardex.wizard'
    _description = 'Asistente Kardex AVCO'

    filter_type = fields.Selection([
        ('month', 'Mensual'),
        ('range', 'Rango de fechas'),
    ], string='Tipo de filtro', default='month', required=True)

    filter_month = fields.Selection(
        selection='_get_month_selection',
        string='Mes',
        default=lambda self: self._default_month(),
    )
    filter_year = fields.Selection(
        selection='_get_year_selection',
        string='Año',
        default=lambda self: str(fields.Date.today().year),
    )

    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: (fields.Date.today().replace(day=1) - timedelta(days=1)).replace(day=1),
    )
    date_to = fields.Date(
        string='Hasta', required=True,
        default=lambda self: fields.Date.today().replace(day=1) - timedelta(days=1),
    )
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        required=True, default=lambda self: self.env.company,
    )
    branch_id = fields.Many2one(
        'res.branch', string='Sucursal',
        domain="[('company_id', '=', company_id)]",
        help='Vacío = todas las sucursales.',
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Almacén',
        domain="[('company_id', '=', company_id)]",
        help='Vacío = todos los almacenes.',
    )
    location_id = fields.Many2one(
        'stock.location', string='Ubicación',
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
        help='Vacío = todas las ubicaciones internas.',
    )
    categ_ids = fields.Many2many(
        'product.category',
        'gn_stock_kardex_wizard_categ_rel',
        'wizard_id', 'categ_id',
        string='Categorías',
        help='Vacío = todas las categorías.',
    )
    product_ids = fields.Many2many(
        'product.product',
        'gn_stock_kardex_wizard_product_rel',
        'wizard_id', 'product_id',
        string='Productos',
        domain="[('is_storable', '=', True)]",
        help='Vacío = todos los productos con movimientos.',
    )

    @api.model
    def _get_month_selection(self):
        return [(str(i), calendar.month_name[i].capitalize()) for i in range(1, 13)]

    @api.model
    def _get_year_selection(self):
        current_year = fields.Date.today().year
        return [(str(y), str(y)) for y in range(current_year - 5, current_year + 2)]

    @api.model
    def _default_month(self):
        prev = fields.Date.today().replace(day=1) - timedelta(days=1)
        return str(prev.month)

    @api.onchange('filter_type', 'filter_month', 'filter_year')
    def _onchange_filter(self):
        if self.filter_type == 'month' and self.filter_month and self.filter_year:
            month = int(self.filter_month)
            year = int(self.filter_year)
            last_day = calendar.monthrange(year, month)[1]
            self.date_from = fields.Date.to_date(f'{year}-{month:02d}-01')
            self.date_to = fields.Date.to_date(f'{year}-{month:02d}-{last_day:02d}')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for w in self:
            if w.date_from and w.date_to and w.date_from > w.date_to:
                raise UserError(_('La fecha inicial no puede ser mayor que la final.'))

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.branch_id and self.branch_id.company_id != self.company_id:
            self.branch_id = False
        if self.warehouse_id and self.warehouse_id.company_id != self.company_id:
            self.warehouse_id = False
        if self.location_id and self.location_id.company_id != self.company_id:
            self.location_id = False

    def _resolve_products(self):
        self.ensure_one()
        if self.product_ids:
            return self.product_ids.filtered(lambda p: p.is_storable)

        extra_clauses = ""
        params = [self.company_id.id, self.date_from, self.date_to]

        if self.branch_id:
            extra_clauses += " AND sm.branch_id = %s"
            params.append(self.branch_id.id)

        if self.warehouse_id:
            extra_clauses += " AND sm.warehouse_id = %s"
            params.append(self.warehouse_id.id)

        if self.location_id:
            extra_clauses += " AND (sm.location_id = %s OR sm.location_dest_id = %s)"
            params.extend([self.location_id.id, self.location_id.id])

        if self.categ_ids:
            extra_clauses += " AND pt.categ_id = ANY(%s)"
            params.append(list(self.categ_ids.ids))

        self.env.cr.execute(f"""
            SELECT DISTINCT r.product_id
              FROM stock_avco_report r
              JOIN product_product pp ON pp.id = r.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
              JOIN stock_move sm ON sm.id = r.id
             WHERE r.company_id = %s
               AND r.date >= %s
               AND r.date <= %s
               AND pt.type = 'consu'
               AND pt.is_storable = true
               AND r.res_model_name = 'stock.move'
               {extra_clauses}
        """, params)
        pids = [row[0] for row in self.env.cr.fetchall()]
        if not pids:
            raise UserError(_('No se encontraron productos almacenables con movimiento en el periodo.'))
        return self.env['product.product'].browse(pids)

    def _get_action_context(self):
        self.ensure_one()
        products = self._resolve_products()
        return {
            'kardex_company_id': self.company_id.id,
            'kardex_branch_id': self.branch_id.id if self.branch_id else False,
            'kardex_branch_name': self.branch_id.name if self.branch_id else '',
            'kardex_warehouse_id': self.warehouse_id.id if self.warehouse_id else False,
            'kardex_warehouse_name': self.warehouse_id.name if self.warehouse_id else '',
            'kardex_location_id': self.location_id.id if self.location_id else False,
            'kardex_location_name': self.location_id.complete_name if self.location_id else '',
            'kardex_location_ids': [self.location_id.id] if self.location_id else [],
            'kardex_product_ids': list(products.ids),
            'kardex_date_from': fields.Date.to_string(self.date_from),
            'kardex_date_to': fields.Date.to_string(self.date_to),
        }

    def action_print_pdf(self):
        self.ensure_one()
        self.product_ids = self._resolve_products()
        return self.env.ref('gn_stock_kardex.action_report_kardex_pdf').report_action(self)

    def action_print_xlsx(self):
        self.ensure_one()
        self.product_ids = self._resolve_products()
        return self.env.ref('gn_stock_kardex.action_report_kardex_xlsx').report_action(self)

    def action_print_summary_pdf(self):
        self.ensure_one()
        self.product_ids = self._resolve_products()
        return self.env.ref('gn_stock_kardex.action_report_kardex_summary_pdf').report_action(self)

    def action_print_summary_xlsx(self):
        self.ensure_one()
        self.product_ids = self._resolve_products()
        return self.env.ref('gn_stock_kardex.action_report_kardex_summary_xlsx').report_action(self)

    def action_open_kardex_preview(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_stock_kardex_preview',
            'name': _('Kardex — valoración'),
            'target': 'current',
            'context': self._get_action_context(),
        }

    def action_open_summary(self):
        self.ensure_one()
        ctx = self._get_action_context()
        ctx['kardex_view_mode'] = 'summary'
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_stock_kardex_preview',
            'name': _('Kardex — resumen'),
            'target': 'current',
            'context': ctx,
        }

    @api.model
    def get_kardex_json(self, company_id, product_ids, date_from, date_to,
                        branch_id=False, warehouse_id=False, location_id=False,
                        location_ids=None):
        return self.env['report.gn_stock_kardex.report_kardex_template'].get_kardex_json(
            company_id, product_ids, date_from, date_to,
            branch_id=branch_id, warehouse_id=warehouse_id,
            location_id=location_id, location_ids=location_ids,
        )

    def _get_report_data(self):
        self.ensure_one()
        products = self._resolve_products()
        report = self.env['report.gn_stock_kardex.report_kardex_template']
        return report._get_kardex_data(self.company_id, products, self.date_from, self.date_to)
