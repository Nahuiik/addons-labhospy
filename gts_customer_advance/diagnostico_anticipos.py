#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para verificar por qué no se muestra el banner de anticipos
en una factura específica.

Uso:
    python3 diagnostico_anticipos.py <nombre_factura> <nombre_cliente>
    
Ejemplo:
    python3 diagnostico_anticipos.py ME2/00001 "ROSA ALPINA SARABIA VIUDA DE EVANGEL"
"""

import sys
import os

# Agregar ruta de Odoo al path
odoo_path = '/home/odoo/src/odoo'
if odoo_path not in sys.path:
    sys.path.insert(0, odoo_path)

import odoo
from odoo import api, SUPERUSER_ID

def diagnostico_anticipos(db_name, invoice_name, partner_name):
    """Ejecuta diagnóstico de anticipos para una factura."""
    
    # Inicializar Odoo
    odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf'])
    registry = odoo.registry(db_name)
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # Buscar la factura
        invoice = env['account.move'].search([
            ('name', '=', invoice_name)
        ], limit=1)
        
        if not invoice:
            print(f"❌ ERROR: No se encontró la factura '{invoice_name}'")
            return
        
        print(f"\n{'='*80}")
        print(f"DIAGNÓSTICO DE ANTICIPOS PARA FACTURA: {invoice_name}")
        print(f"{'='*80}\n")
        
        # Información básica de la factura
        print("📋 INFORMACIÓN DE LA FACTURA:")
        print(f"   ID: {invoice.id}")
        print(f"   Nombre: {invoice.name}")
        print(f"   Tipo: {invoice.move_type}")
        print(f"   Estado: {invoice.state}")
        print(f"   Cliente: {invoice.partner_id.name if invoice.partner_id else 'Sin cliente'}")
        print(f"   Compañía: {invoice.company_id.name if invoice.company_id else 'Sin compañía'}")
        print(f"   Moneda: {invoice.currency_id.name if invoice.currency_id else 'Sin moneda'}")
        print(f"   Saldo pendiente: {invoice.amount_residual}")
        print(f"   Total: {invoice.amount_total}")
        
        # Verificar condiciones del banner
        print(f"\n{'='*80}")
        print("🔍 VERIFICACIÓN DE CONDICIONES DEL BANNER:")
        print(f"{'='*80}\n")
        
        condiciones = {
            'move_type == out_invoice': invoice.move_type == 'out_invoice',
            'state == posted': invoice.state == 'posted',
            'partner_id existe': bool(invoice.partner_id),
            'company_id existe': bool(invoice.company_id),
            'amount_residual > 0': invoice.amount_residual > 0,
        }
        
        for condicion, resultado in condiciones.items():
            estado = "✅" if resultado else "❌"
            print(f"   {estado} {condicion}: {resultado}")
        
        # Verificar campo dte_accepted_for_advances
        print(f"\n   Verificando campo 'dte_accepted_for_advances':")
        invoice.invalidate_recordset(['dte_accepted_for_advances'])
        invoice._compute_dte_accepted_for_advances()
        dte_accepted = invoice.dte_accepted_for_advances
        print(f"   {'✅' if dte_accepted else '❌'} dte_accepted_for_advances: {dte_accepted}")
        
        if hasattr(invoice, 'l10n_sv_electronic_dte_state'):
            dte_state = invoice.l10n_sv_electronic_dte_state or 'No aplica'
            print(f"   Estado DTE: {dte_state}")
        
        # Verificar anticipos disponibles
        print(f"\n{'='*80}")
        print("💰 VERIFICACIÓN DE ANTICIPOS DISPONIBLES:")
        print(f"{'='*80}\n")
        
        if not invoice.partner_id:
            print("   ❌ No hay cliente asignado. No se pueden buscar anticipos.")
            return
        
        if not invoice.company_id:
            print("   ❌ No hay compañía asignada. No se pueden buscar anticipos.")
            return
        
        # Buscar todos los anticipos del cliente
        all_advances = env['account.payment'].search([
            ('is_advance', '=', True),
            ('partner_id', '=', invoice.partner_id.id),
            ('company_id', '=', invoice.company_id.id),
        ])
        
        print(f"   Total de anticipos del cliente (todos los estados): {len(all_advances)}")
        
        if all_advances:
            print(f"\n   Detalle de anticipos:")
            for adv in all_advances[:10]:  # Mostrar máximo 10
                print(f"      - {adv.name or 'Sin nombre'}:")
                print(f"        Estado: {adv.state}")
                print(f"        Monto: {adv.amount}")
                print(f"        Moneda: {adv.currency_id.name if adv.currency_id else 'Sin moneda'}")
                print(f"        Saldo disponible: {adv.advance_available_amount}")
                print(f"        Total aplicado: {adv.advance_applied_total}")
                print(f"        Partner type: {adv.partner_type}")
        
        # Buscar anticipos disponibles usando el método del módulo
        Payment = env['account.payment']
        available_advances = Payment._get_available_advances_for_partner(
            invoice.partner_id.id,
            invoice.company_id.id,
            invoice.currency_id.id if invoice.currency_id else None,
            partner_type='customer'
        )
        
        print(f"\n   Anticipos disponibles encontrados: {len(available_advances)}")
        
        if available_advances:
            print(f"\n   Detalle de anticipos disponibles:")
            for adv in available_advances:
                print(f"      - {adv.name or 'Sin nombre'}:")
                print(f"        Estado: {adv.state}")
                print(f"        Monto: {adv.amount}")
                print(f"        Saldo disponible: {adv.advance_available_amount}")
                print(f"        Moneda: {adv.currency_id.name if adv.currency_id else 'Sin moneda'}")
        else:
            print(f"\n   ⚠️  No se encontraron anticipos disponibles.")
            print(f"   Verificando por qué no están disponibles...")
            
            # Verificar por estado
            estados_validos = ['in_process', 'paid']
            anticipos_estado_invalido = all_advances.filtered(
                lambda a: a.state not in estados_validos
            )
            if anticipos_estado_invalido:
                print(f"\n   Anticipos con estado inválido ({len(anticipos_estado_invalido)}):")
                for adv in anticipos_estado_invalido[:5]:
                    print(f"      - {adv.name}: Estado={adv.state} (debe ser 'in_process' o 'paid')")
            
            # Verificar por saldo disponible
            anticipos_sin_saldo = all_advances.filtered(
                lambda a: a.advance_available_amount <= 0
            )
            if anticipos_sin_saldo:
                print(f"\n   Anticipos sin saldo disponible ({len(anticipos_sin_saldo)}):")
                for adv in anticipos_sin_saldo[:5]:
                    print(f"      - {adv.name}: Disponible={adv.advance_available_amount}, Aplicado={adv.advance_applied_total}")
            
            # Verificar por moneda
            if invoice.currency_id:
                anticipos_moneda_diferente = all_advances.filtered(
                    lambda a: a.currency_id.id != invoice.currency_id.id
                )
                if anticipos_moneda_diferente:
                    print(f"\n   Anticipos en moneda diferente ({len(anticipos_moneda_diferente)}):")
                    for adv in anticipos_moneda_diferente[:5]:
                        print(f"      - {adv.name}: Moneda={adv.currency_id.name if adv.currency_id else 'Sin moneda'} (factura usa {invoice.currency_id.name})")
        
        # Recalcular campos computed
        print(f"\n{'='*80}")
        print("🔄 RECÁLCULO DE CAMPOS COMPUTED:")
        print(f"{'='*80}\n")
        
        invoice.invalidate_recordset(['has_available_advances', 'available_advances_amount', 'available_advances_count'])
        invoice._compute_has_available_advances()
        
        print(f"   has_available_advances: {invoice.has_available_advances}")
        print(f"   available_advances_amount: {invoice.available_advances_amount}")
        print(f"   available_advances_count: {invoice.available_advances_count}")
        
        # Verificar si el banner debería mostrarse
        print(f"\n{'='*80}")
        print("🎯 RESULTADO FINAL:")
        print(f"{'='*80}\n")
        
        banner_visible = (
            invoice.move_type == 'out_invoice' and
            invoice.has_available_advances and
            invoice.state == 'posted' and
            invoice.dte_accepted_for_advances
        )
        
        print(f"   ¿El banner debería mostrarse? {'✅ SÍ' if banner_visible else '❌ NO'}\n")
        
        if not banner_visible:
            print("   Razones por las que NO se muestra:")
            if invoice.move_type != 'out_invoice':
                print("      ❌ No es factura de cliente")
            if not invoice.has_available_advances:
                print("      ❌ No hay anticipos disponibles")
            if invoice.state != 'posted':
                print("      ❌ La factura no está publicada")
            if not invoice.dte_accepted_for_advances:
                print("      ❌ El DTE no está aceptado (si aplica)")
        
        print(f"\n{'='*80}\n")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python3 diagnostico_anticipos.py <nombre_factura> <nombre_cliente>")
        print("Ejemplo: python3 diagnostico_anticipos.py ME2/00001 'ROSA ALPINA SARABIA VIUDA DE EVANGEL'")
        sys.exit(1)
    
    invoice_name = sys.argv[1]
    partner_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Obtener nombre de la base de datos desde configuración
    db_name = os.environ.get('DB_NAME', 'realeza')
    
    diagnostico_anticipos(db_name, invoice_name, partner_name)
