# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo import _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    for_sale_receipt = fields.Boolean(
        string="Para recibos de venta",
        default=False,
        help="Marcar este diario como disponible para recibos de venta en el módulo gn_sale_receipt. Solo disponible para diarios tipo Misceláneo.",
    )
    
    def write(self, vals):
        """Validar que solo diarios tipo 'general' puedan marcarse como para recibos de venta"""
        # Si se intenta marcar for_sale_receipt en un diario que no es tipo 'general'
        if 'for_sale_receipt' in vals and vals['for_sale_receipt']:
            for journal in self:
                journal_type = vals.get('type', journal.type)
                if journal_type != 'general':
                    raise ValidationError(
                        _("Solo los diarios tipo 'Misceláneo' pueden marcarse como 'Para recibos de venta'.")
                    )
        
        # Si se cambia el tipo de diario a algo distinto de 'general', desmarcar for_sale_receipt
        if 'type' in vals and vals['type'] != 'general':
            for journal in self:
                if journal.for_sale_receipt:
                    vals['for_sale_receipt'] = False
        
        return super().write(vals)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Validar que solo diarios tipo 'general' puedan marcarse como para recibos de venta"""
        for vals in vals_list:
            if vals.get('for_sale_receipt') and vals.get('type') != 'general':
                raise ValidationError(
                    _("Solo los diarios tipo 'Misceláneo' pueden marcarse como 'Para recibos de venta'.")
                )
        return super().create(vals_list)

