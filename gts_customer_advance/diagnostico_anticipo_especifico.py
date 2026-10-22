#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para verificar un anticipo específico y por qué no se muestra el banner.

Uso:
    python3 diagnostico_anticipo_especifico.py <nombre_anticipo>
    
Ejemplo:
    python3 diagnostico_anticipo_especifico.py DEP/CGMETRO1/00003
"""

import sys
import os

# Agregar ruta de Odoo al path
odoo_path = '/home/odoo/src/odoo'
if odoo_path not in sys.path:
    sys.path.insert(0, odoo_path)

import odoo
from odoo import api, SUPERUSER_ID
from odoo.service import db

def diagnostico_anticipo(db_name, advance_name):
    """Ejecuta diagnóstico de un anticipo específico."""
    
    # Inicializar Odoo
    odoo.tools.config.parse_config(['-c', '/home/odoo/.odoorc'])
    
    # Conectar a la base de datos
    db.initialize([db_name])
    registry = odoo.registry(db_name)
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # Buscar el anticipo
        advance = env['account.payment'].search([
            ('name', '=', advance_name)
        ], limit=1)
        
        if not advance:
            print(f"❌ ERROR: No se encontró el anticipo '{advance_name}'")
            return
        
        print(f"\n{'='*80}")
        print(f"DIAGNÓSTICO DEL ANTICIPO: {advance_name}")
        print(f"{'='*80}\n")
        
        # Información del anticipo
        print("💰 INFORMACIÓN DEL ANTICIPO:")
        print(f"   ID: {advance.id}")
        print(f"   Nombre: {advance.name}")
        print(f"   Es anticipo: {advance.is_advance}")
        print(f"   Estado: {advance.state}")
        print(f"   Cliente: {advance.partner_id.name if advance.partner_id else 'Sin cliente'}")
        print(f"   Partner ID: {advance.partner_id.id if advance.partner_id else 'N/A'}")
        print(f"   Compañía: {advance.company_id.name if advance.company_id else 'Sin compañía'}")
        print(f"   Company ID: {advance.company_id.id if advance.company_id else 'N/A'}")
        print(f"   Moneda: {advance.currency_id.name if advance.currency_id else 'Sin moneda'}")
        print(f"   Currency ID: {advance.currency_id.id if advance.currency_id else 'N/A'}")
        print(f"   Monto: {advance.amount}")
        print(f"   Partner Type: {advance.partner_type}")
        
        # Recalcular saldo disponible
        print(f"\n   Recalculando saldo disponible...")
        advance.invalidate_recordset(['advance_available_amount', 'advance_applied_total'])
        advance._compute_advance_available_amount()
        print(f"   Saldo disponible: {advance.advance_available_amount}")
        print(f"   Total aplicado: {advance.advance_applied_total}")
        
        # Verificar aplicaciones
        print(f"\n   Aplicaciones del anticipo:")
        if advance.advance_link_ids:
            for link in advance.advance_link_ids:
                print(f"      - Factura: {link.move_id.name if link.move_id else 'N/A'}")
                print(f"        Monto: {link.amount}")
                print(f"        Estado: {link.state}")
        else:
            print(f"      No hay aplicaciones")
        
        # Buscar facturas del mismo cliente
        if not advance.partner_id:
            print(f"\n❌ ERROR: El anticipo no tiene cliente asignado")
            return
        
        if not advance.company_id:
            print(f"\n❌ ERROR: El anticipo no tiene compañía asignada")
            return
        
        print(f"\n{'='*80}")
        print("📋 FACTURAS DEL CLIENTE QUE DEBERÍAN MOSTRAR EL BANNER:")
        print(f"{'='*80}\n")
        
        # Buscar facturas del cliente
        invoices = env['account.move'].search([
            ('partner_id', '=', advance.partner_id.id),
            ('company_id', '=', advance.company_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ])
        
        print(f"   Total de facturas publicadas del cliente: {len(invoices)}")
        
        if invoices:
            print(f"\n   Facturas con saldo pendiente:")
            invoices_with_residual = invoices.filtered(lambda inv: inv.amount_residual > 0)
            print(f"   Cantidad: {len(invoices_with_residual)}")
            
            for invoice in invoices_with_residual[:10]:  # Mostrar máximo 10
                print(f"\n   📄 Factura: {invoice.name}")
                print(f"      Cliente: {invoice.partner_id.name}")
                print(f"      Estado: {invoice.state}")
                print(f"      Moneda: {invoice.currency_id.name if invoice.currency_id else 'Sin moneda'}")
                print(f"      Saldo pendiente: {invoice.amount_residual}")
                print(f"      Total: {invoice.amount_total}")
                
                # Verificar DTE
                invoice.invalidate_recordset(['dte_accepted_for_advances'])
                invoice._compute_dte_accepted_for_advances()
                dte_accepted = invoice.dte_accepted_for_advances
                if hasattr(invoice, 'l10n_sv_electronic_dte_state'):
                    dte_state = invoice.l10n_sv_electronic_dte_state or 'No aplica'
                    print(f"      Estado DTE: {dte_state}")
                print(f"      DTE aceptado para anticipos: {dte_accepted}")
                
                # Verificar anticipos disponibles
                invoice.invalidate_recordset(['has_available_advances', 'available_advances_amount', 'available_advances_count'])
                invoice._compute_has_available_advances()
                
                print(f"      has_available_advances: {invoice.has_available_advances}")
                print(f"      available_advances_amount: {invoice.available_advances_amount}")
                print(f"      available_advances_count: {invoice.available_advances_count}")
                
                # Verificar si el anticipo específico está disponible
                Payment = env['account.payment']
                available_advances = Payment._get_available_advances_for_partner(
                    invoice.partner_id.id,
                    invoice.company_id.id,
                    invoice.currency_id.id if invoice.currency_id else None,
                    partner_type='customer'
                )
                
                advance_in_list = advance in available_advances
                print(f"      ¿El anticipo {advance_name} está en la lista disponible? {advance_in_list}")
                
                if advance_in_list:
                    print(f"      ✅ El anticipo debería aparecer para esta factura")
                else:
                    print(f"      ❌ El anticipo NO está disponible para esta factura")
                    # Verificar por qué
                    if advance.state not in ('in_process', 'paid'):
                        print(f"         Razón: Estado inválido ({advance.state})")
                    if advance.advance_available_amount <= 0:
                        print(f"         Razón: Sin saldo disponible ({advance.advance_available_amount})")
                    if invoice.currency_id and advance.currency_id.id != invoice.currency_id.id:
                        print(f"         Razón: Moneda diferente (anticipo: {advance.currency_id.name}, factura: {invoice.currency_id.name})")
                
                # Verificar condiciones del banner
                banner_visible = (
                    invoice.move_type == 'out_invoice' and
                    invoice.has_available_advances and
                    invoice.state == 'posted' and
                    invoice.dte_accepted_for_advances
                )
                
                print(f"      ¿El banner debería mostrarse? {'✅ SÍ' if banner_visible else '❌ NO'}")
                
                if not banner_visible:
                    print(f"      Razones:")
                    if invoice.move_type != 'out_invoice':
                        print(f"         ❌ No es factura de cliente")
                    if not invoice.has_available_advances:
                        print(f"         ❌ has_available_advances = False")
                    if invoice.state != 'posted':
                        print(f"         ❌ Estado no es 'posted'")
                    if not invoice.dte_accepted_for_advances:
                        print(f"         ❌ DTE no aceptado")
        else:
            print(f"   No hay facturas publicadas del cliente")
        
        print(f"\n{'='*80}\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python3 diagnostico_anticipo_especifico.py <nombre_anticipo>")
        print("Ejemplo: python3 diagnostico_anticipo_especifico.py DEP/CGMETRO1/00003")
        sys.exit(1)
    
    advance_name = sys.argv[1]
    db_name = os.environ.get('DB_NAME', 'realeza')
    
    diagnostico_anticipo(db_name, advance_name)
