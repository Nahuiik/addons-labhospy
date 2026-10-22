# -*- coding: utf-8 -*-
"""
Hooks de inicialización para el módulo gts_customer_advance
"""

from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Hook ejecutado después de instalar/actualizar el módulo.
    Recalcula advance_available_amount en todos los anticipos existentes.
    """
    _logger.info("Recalculando advance_available_amount en anticipos existentes...")
    
    Payment = env['account.payment']
    payments = Payment.search([('is_advance', '=', True)])
    
    if payments:
        _logger.info(f"Encontrados {len(payments)} anticipos para recalcular")
        # Invalidar el campo para forzar recálculo
        payments.invalidate_recordset(['advance_available_amount', 'advance_applied_total'])
        # Recalcular
        payments._compute_advance_available_amount()
        env.cr.commit()
        
        # Verificar resultados
        with_available = payments.filtered(lambda p: p.advance_available_amount > 0)
        _logger.info(f"Recálculo completado. Anticipos con saldo disponible: {len(with_available)}")
    else:
        _logger.info("No se encontraron anticipos para recalcular")
