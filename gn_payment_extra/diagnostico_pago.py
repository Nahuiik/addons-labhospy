#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para verificar por qué un pago no aparece en el reporte
"""
import sys
import os

# Agregar el path de Odoo
sys.path.insert(0, '/home/odoo/src/odoo')

import odoo
from odoo import api, SUPERUSER_ID

# Configurar Odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/realeza.conf'] if os.path.exists('/etc/odoo/realeza.conf') else [])
odoo.tools.config['db_name'] = 'REALEZA'

# Inicializar Odoo
odoo.service.db.initialize()
registry = odoo.registry('REALEZA')

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Buscar el pago específico
    payment_name = 'PBNK1/2026/00003'
    payment = env['account.payment'].search([('name', '=', payment_name)], limit=1)
    
    if not payment:
        print(f"❌ No se encontró el pago: {payment_name}")
        print("\nBuscando pagos similares...")
        similar = env['account.payment'].search([('name', 'like', 'PBNK1/2026/%')], limit=10)
        for p in similar:
            print(f"  - {p.name} (Estado: {p.state})")
    else:
        print(f"✅ Pago encontrado: {payment.name}")
        print(f"\n📋 Información del pago:")
        print(f"  - ID: {payment.id}")
        print(f"  - Estado: {payment.state}")
        print(f"  - Fecha: {payment.date}")
        print(f"  - Tipo de pago: {payment.payment_type}")
        print(f"  - Tipo de socio: {payment.partner_type}")
        print(f"  - Diario: {payment.journal_id.name if payment.journal_id else 'Sin diario'}")
        print(f"  - Método de pago: {payment.payment_method_type}")
        print(f"  - Meses: {payment.months}")
        print(f"  - Convenio: {payment.card_agreement_id.name if payment.card_agreement_id else 'Sin convenio'}")
        print(f"  - Monto: {payment.amount}")
        print(f"  - Comisión %: {payment.commission_percentage}")
        print(f"  - Monto sin IVA: {payment.amount_without_vat}")
        print(f"  - Comisión: {payment.commission_amount}")
        print(f"  - Total deducciones: {payment.total_deductions}")
        print(f"  - Monto a recibir: {payment.amount_to_receive}")
        
        # Verificar condiciones del reporte
        print(f"\n🔍 Verificación de condiciones del reporte:")
        print(f"  - Estado = 'posted': {'✅' if payment.state == 'posted' else '❌'} ({payment.state})")
        print(f"  - Tipo de pago = 'inbound': {'✅' if payment.payment_type == 'inbound' else '❌'} ({payment.payment_type})")
        print(f"  - Tipo de socio = 'customer': {'✅' if payment.partner_type == 'customer' else '❌'} ({payment.partner_type})")
        print(f"  - Método de pago != 'none': {'✅' if payment.payment_method_type and payment.payment_method_type != 'none' else '❌'} ({payment.payment_method_type})")
        print(f"  - Tiene convenio: {'✅' if payment.card_agreement_id else '❌'}")
        
        # Verificar si aparecería en el reporte con fechas actuales
        from datetime import date, timedelta
        date_from = date.today() - timedelta(days=30)
        date_to = date.today()
        
        print(f"\n📅 Verificación con rango de fechas ({date_from} a {date_to}):")
        print(f"  - Fecha del pago en rango: {'✅' if date_from <= payment.date <= date_to else '❌'} ({payment.date})")
        
        # Buscar pagos similares que sí aparezcan
        print(f"\n🔎 Buscando otros pagos que cumplan los criterios:")
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'posted'),
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
        ]
        similar_payments = env['account.payment'].search(domain, limit=10)
        similar_payments = similar_payments.filtered(lambda p: p.payment_method_type and p.payment_method_type != 'none')
        
        print(f"  - Pagos encontrados: {len(similar_payments)}")
        for p in similar_payments[:5]:
            print(f"    • {p.name} - Método: {p.payment_method_type} - Convenio: {p.card_agreement_id.name if p.card_agreement_id else 'Sin convenio'}")
