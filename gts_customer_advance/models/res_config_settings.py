# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    advance_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Anticipo de Clientes',
        domain=[('active', '=', True), ('reconcile', '=', True)],
        config_parameter='gts_customer_advance.advance_account_id',
        help='Cuenta conciliable para anticipos de clientes por defecto'
    )
    vendor_advance_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Anticipo de Proveedores',
        domain=[('active', '=', True), ('reconcile', '=', True)],
        config_parameter='gts_customer_advance.vendor_advance_account_id',
        help='Cuenta conciliable para anticipos de proveedores por defecto'
    )
    customer_advance_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Secuencia Anticipos de Clientes',
        domain=[('code', '=', 'customer.advance')],
        config_parameter='gts_customer_advance.customer_advance_sequence_id',
        help='Secuencia para numerar anticipos de clientes'
    )
    vendor_advance_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Secuencia Anticipos de Proveedores',
        domain=[('code', '=', 'vendor.advance')],
        config_parameter='gts_customer_advance.vendor_advance_sequence_id',
        help='Secuencia para numerar anticipos de proveedores'
    )
    reclass_journal_id = fields.Many2one(
        'account.journal',
        string='Diario de Reclasificación',
        domain=[('type', '=', 'general')],
        config_parameter='gts_customer_advance.reclass_journal_id',
        help='Diario contable usado para los asientos de reclasificación de anticipos'
    )
    allow_split_advance = fields.Boolean(
        string='Permitir Fraccionar Anticipo',
        default=True,
        config_parameter='gts_customer_advance.allow_split_advance',
        help='Permite aplicar un anticipo a múltiples facturas (fraccionamiento)'
    )
    reclass_date_source = fields.Selection([
        ('invoice', 'Fecha de la Factura'),
        ('today', 'Fecha Actual'),
    ],
        string='Origen de Fecha del Asiento de Reclasificación',
        default='invoice',
        config_parameter='gts_customer_advance.reclass_date_source',
        help='Define qué fecha usar para el asiento de reclasificación'
    )

    @api.model
    def _get_default_advance_account_id(self):
        """Obtiene la cuenta de anticipo por defecto desde configuración"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'gts_customer_advance.advance_account_id'
        )

    @api.model
    def _get_default_reclass_journal_id(self):
        """Obtiene el diario de reclasificación por defecto"""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'gts_customer_advance.reclass_journal_id'
        )
        if param:
            return int(param)
        # Si no está configurado, buscar el diario general
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        return journal.id if journal else False

    @api.constrains('advance_account_id')
    def _check_advance_account(self):
        """Valida que la cuenta de anticipo sea conciliable"""
        for record in self:
            if record.advance_account_id and not record.advance_account_id.reconcile:
                raise ValidationError(_(
                    'La cuenta de anticipo "%s" debe ser conciliable.' % record.advance_account_id.name
                ))

