# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SalesDashboardTarget(models.Model):
    _name = 'sales.dashboard.target'
    _description = 'Meta comercial del dashboard'
    _order = 'date_from desc, company_id'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    branch_id = fields.Many2one('res.branch', string='Sucursal')
    team_id = fields.Many2one('crm.team', string='Equipo comercial')
    user_id = fields.Many2one('res.users', string='Vendedor')
    product_id = fields.Many2one('product.product', string='Producto')
    category_id = fields.Many2one('product.category', string='Categoría')
    period_type = fields.Selection([
        ('monthly', 'Mensual'),
        ('quarterly', 'Trimestral'),
        ('yearly', 'Anual'),
    ], required=True, default='monthly')
    date_from = fields.Date(required=True, index=True)
    date_to = fields.Date(required=True, index=True)
    target_sales = fields.Float(string='Meta ventas', digits=(16, 2))
    target_margin = fields.Float(string='Meta margen', digits=(16, 2))
    target_orders = fields.Integer(string='Meta pedidos')
    target_new_customers = fields.Integer(string='Meta clientes nuevos')
    target_conversion = fields.Float(string='Meta conversión (%)', digits=(5, 2))
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_('La fecha inicial debe ser anterior a la final.'))

    @api.depends('period_type', 'date_from', 'branch_id', 'team_id', 'user_id')
    def _compute_name(self):
        for rec in self:
            parts = [rec.period_type or '', rec.date_from and rec.date_from.strftime('%Y-%m') or '']
            if rec.user_id:
                parts.append(rec.user_id.name)
            elif rec.team_id:
                parts.append(rec.team_id.name)
            elif rec.branch_id:
                parts.append(rec.branch_id.name)
            rec.name = ' – '.join(p for p in parts if p)

    @api.constrains('branch_id', 'team_id', 'user_id', 'product_id', 'category_id', 'date_from', 'date_to')
    def _check_unique_scope(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('date_from', '=', rec.date_from),
                ('date_to', '=', rec.date_to),
                ('branch_id', '=', rec.branch_id.id),
                ('team_id', '=', rec.team_id.id),
                ('user_id', '=', rec.user_id.id),
                ('product_id', '=', rec.product_id.id),
                ('category_id', '=', rec.category_id.id),
            ]
            if self.search_count(domain):
                raise ValidationError(_('Ya existe una meta para la misma combinación de alcance y período.'))
