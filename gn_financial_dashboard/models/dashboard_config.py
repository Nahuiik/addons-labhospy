# -*- coding: utf-8 -*-
"""Configuración del Tablero Financiero.

Modelo persistente (uno por compañía) que centraliza:
- Umbrales de las alertas (antes quemados en código).
- Personalización visual (color, modo compacto, visibilidad y orden de
  secciones, moneda visible).

Se obtiene siempre vía :meth:`get_or_create` para garantizar que cada compañía
disponga de una configuración con valores por defecto sensatos.
"""
from odoo import api, fields, models


# Claves de sección reconocidas por el frontend (para visibilidad/orden).
SECTION_KEYS = (
    'profitability', 'liquidity', 'cashflow', 'aging',
    'expense_ranking', 'partner_ranking', 'analysis', 'data_quality',
)


class GnFinancialDashboardConfig(models.Model):
    _name = 'gn.financial.dashboard.config'
    _description = 'Configuración del Tablero Financiero'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
        ondelete='cascade', index=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda', readonly=True,
    )

    # ------------------------------------------------------------------
    # Umbrales de alertas (sustituyen valores fijos en código)
    # ------------------------------------------------------------------
    min_net_margin = fields.Float(
        string='Margen neto mínimo (%)', default=5.0,
        help='Por debajo de este margen neto se genera una alerta.',
    )
    max_overdue_receivable_pct = fields.Float(
        string='% máx. cartera vencida', default=30.0,
        help='% de cartera por cobrar vencida que dispara la alerta.',
    )
    max_over_120_pct = fields.Float(
        string='% máx. cartera +120 días', default=15.0,
        help='% de cartera por cobrar a más de 120 días que dispara la alerta.',
    )
    min_current_ratio = fields.Float(
        string='Razón corriente mínima', default=1.0,
        help='Activo corriente / pasivo corriente mínimo aceptable.',
    )
    min_working_capital = fields.Monetary(
        string='Capital de trabajo mínimo', default=0.0,
        currency_field='currency_id',
    )
    min_cash_flow = fields.Monetary(
        string='Flujo de caja mínimo', default=0.0,
        currency_field='currency_id',
    )
    max_expense_ratio = fields.Float(
        string='% máx. gasto sobre ingresos', default=70.0,
        help='% de gastos respecto a ingresos que dispara la alerta.',
    )

    # ------------------------------------------------------------------
    # Mapeo de cuentas para EBIT/EBITDA y cobertura de intereses
    # ------------------------------------------------------------------
    # No se infieren por account_type, por eso son configurables.
    interest_account_ids = fields.Many2many(
        'account.account',
        relation='gn_fd_config_interest_acc_rel',
        column1='config_id', column2='account_id',
        string='Cuentas de intereses',
        help='Cuentas de gasto financiero por intereses (para calcular EBIT, '
             'EBITDA y la cobertura de intereses).',
    )
    tax_expense_account_ids = fields.Many2many(
        'account.account',
        relation='gn_fd_config_tax_acc_rel',
        column1='config_id', column2='account_id',
        string='Cuentas de impuestos sobre la renta',
        help='Cuentas de gasto por impuesto sobre la renta (para calcular EBIT '
             'y EBITDA).',
    )
    depreciation_account_ids = fields.Many2many(
        'account.account',
        relation='gn_fd_config_depr_acc_rel',
        column1='config_id', column2='account_id',
        string='Cuentas de depreciación/amortización',
        help='Cuentas adicionales que deben sumarse a la depreciación. Si está '
             'vacío, se usan automáticamente todas las cuentas con tipo '
             'expense_depreciation.',
    )
    inventory_account_ids = fields.Many2many(
        'account.account',
        relation='gn_fd_config_inv_acc_rel',
        column1='config_id', column2='account_id',
        string='Cuentas de inventario',
        help='Cuentas usadas para calcular el inventario promedio (rotación de '
             'inventario). Si está vacío, se asume que no aplica.',
    )

    # ------------------------------------------------------------------
    # Personalización visual
    # ------------------------------------------------------------------
    primary_color = fields.Char(
        string='Color principal', default='#5b2c6f',
        help='Color base del tablero (hex).',
    )
    compact_mode = fields.Boolean(string='Modo compacto', default=False)
    show_currency = fields.Boolean(string='Mostrar moneda', default=True)

    show_profitability = fields.Boolean(string='Rentabilidad', default=True)
    show_liquidity = fields.Boolean(string='Liquidez y balance', default=True)
    show_cashflow = fields.Boolean(string='Flujo de caja', default=True)
    show_aging = fields.Boolean(string='Cartera por antigüedad', default=True)
    show_expense_ranking = fields.Boolean(string='Ranking de gastos', default=True)
    show_partner_ranking = fields.Boolean(string='Ranking de terceros', default=True)
    show_analysis = fields.Boolean(string='Análisis automático', default=True)
    show_data_quality = fields.Boolean(string='Calidad de datos', default=True)

    # Orden de secciones (menor = primero).
    seq_profitability = fields.Integer(string='Orden rentabilidad', default=10)
    seq_liquidity = fields.Integer(string='Orden liquidez', default=20)
    seq_cashflow = fields.Integer(string='Orden flujo de caja', default=30)
    seq_aging = fields.Integer(string='Orden cartera', default=40)
    seq_expense_ranking = fields.Integer(string='Orden ranking gastos', default=50)
    seq_partner_ranking = fields.Integer(string='Orden ranking terceros', default=60)
    seq_analysis = fields.Integer(string='Orden análisis', default=70)
    seq_data_quality = fields.Integer(string='Orden calidad de datos', default=80)

    _company_uniq = models.Constraint(
        'unique(company_id)',
        'Ya existe una configuración para esta compañía.',
    )

    @api.model
    def get_or_create(self, company):
        """Devuelve (creando si hace falta) la config de ``company``."""
        config = self.sudo().search(
            [('company_id', '=', company.id)], limit=1,
        )
        if not config:
            config = self.sudo().create({'company_id': company.id})
        return config

    def to_payload(self):
        """Serializa la configuración para el frontend/exportaciones."""
        self.ensure_one()
        sections = []
        for key in SECTION_KEYS:
            sections.append({
                'key': key,
                'visible': bool(self['show_%s' % key]),
                'sequence': self['seq_%s' % key],
            })
        sections.sort(key=lambda s: s['sequence'])
        return {
            'thresholds': {
                'min_net_margin': self.min_net_margin,
                'max_overdue_receivable_pct': self.max_overdue_receivable_pct,
                'max_over_120_pct': self.max_over_120_pct,
                'min_current_ratio': self.min_current_ratio,
                'min_working_capital': self.min_working_capital,
                'min_cash_flow': self.min_cash_flow,
                'max_expense_ratio': self.max_expense_ratio,
            },
            # Mapeo de cuentas para EBIT/EBITDA/cobertura (consumido por el
            # backend, no se renderiza directamente en el frontend).
            'account_maps': {
                'interest': self.interest_account_ids.ids,
                'tax': self.tax_expense_account_ids.ids,
                'depreciation': self.depreciation_account_ids.ids,
                'inventory': self.inventory_account_ids.ids,
            },
            'theme': {
                'primary_color': self.primary_color or '#5b2c6f',
                'compact_mode': self.compact_mode,
                'show_currency': self.show_currency,
            },
            'sections': sections,
        }
