#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pruebas funcionales para el módulo l10n_hn_stock
"""

import sys
sys.path.insert(0, '/home/odoo/src/odoo')

import odoo
from odoo import api, SUPERUSER_ID

def run_tests():
    """Ejecutar pruebas funcionales"""
    print("=" * 60)
    print("PRUEBAS FUNCIONALES DEL MÓDULO l10n_hn_stock")
    print("=" * 60)
    
    odoo.tools.config.parse_config(['-d', 'LABHOSPY', '--stop-after-init'])
    registry = odoo.registry('LABHOSPY')
    cr = registry.cursor()
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    results = []
    
    # PRUEBA 1: Verificar instalación
    print("\n=== PRUEBA 1: Verificación de instalación ===")
    try:
        module = env['ir.module.module'].search([
            ('name', '=', 'l10n_hn_stock'),
            ('state', '=', 'installed')
        ])
        if module:
            print("✓ Módulo l10n_hn_stock está instalado")
            results.append(True)
        else:
            print("✗ Módulo NO está instalado")
            results.append(False)
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append(False)
    
    # PRUEBA 2: Verificar grupos de seguridad
    print("\n=== PRUEBA 2: Grupos de seguridad ===")
    try:
        groups = [
            'l10n_hn_stock.group_allow_edit_sale_price_quotation',
            'l10n_hn_stock.group_allow_confirm_sale_view_docs',
            'l10n_hn_stock.group_view_costs_margins',
            'l10n_hn_stock.group_allow_sell_below_cost',
        ]
        all_ok = True
        for group_xmlid in groups:
            try:
                group = env.ref(group_xmlid)
                print(f"✓ {group_xmlid}: {group.name}")
            except Exception as e:
                print(f"✗ {group_xmlid}: {e}")
                all_ok = False
        results.append(all_ok)
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append(False)
    
    # PRUEBA 3: Verificar campos en modelos
    print("\n=== PRUEBA 3: Campos en modelos ===")
    try:
        all_ok = True
        
        # stock.picking
        picking_fields = ['hn_remission_enabled', 'salesperson_id', 'invoice_name', 'hn_remission_number']
        for field_name in picking_fields:
            if field_name in env['stock.picking']._fields:
                print(f"✓ stock.picking.{field_name}")
            else:
                print(f"✗ stock.picking.{field_name} NO existe")
                all_ok = False
        
        # sale.order
        sale_fields = ['margin', 'margin_percent']
        for field_name in sale_fields:
            if field_name in env['sale.order']._fields:
                print(f"✓ sale.order.{field_name}")
            else:
                print(f"✗ sale.order.{field_name} NO existe")
                all_ok = False
        
        # res.company
        if 'no_negative_stock' in env['res.company']._fields:
            print(f"✓ res.company.no_negative_stock")
        else:
            print(f"✗ res.company.no_negative_stock NO existe")
            all_ok = False
        
        results.append(all_ok)
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append(False)
    
    # PRUEBA 4: Verificar secuencia
    print("\n=== PRUEBA 4: Secuencia de remisión ===")
    try:
        sequence = env.ref('l10n_hn_stock.seq_hn_remission')
        print(f"✓ Secuencia existe: {sequence.name} (código: {sequence.code})")
        results.append(True)
    except Exception as e:
        print(f"✗ Secuencia NO existe: {e}")
        results.append(False)
    
    # PRUEBA 5: Verificar métodos
    print("\n=== PRUEBA 5: Métodos en modelos ===")
    try:
        all_ok = True
        picking_model = env['stock.picking']
        methods = ['action_generate_remission_sequence', 'action_print_remission_guide']
        for method_name in methods:
            if hasattr(picking_model, method_name):
                print(f"✓ stock.picking.{method_name}")
            else:
                print(f"✗ stock.picking.{method_name} NO existe")
                all_ok = False
        results.append(all_ok)
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append(False)
    
    # PRUEBA 6: Verificar reporte
    print("\n=== PRUEBA 6: Reporte de remisión ===")
    try:
        report = env.ref('l10n_hn_stock.action_report_remission')
        print(f"✓ Reporte existe: {report.name}")
        results.append(True)
    except Exception as e:
        print(f"✗ Reporte NO existe: {e}")
        results.append(False)
    
    cr.close()
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Total: {passed}/{total} pruebas pasadas")
    
    if passed == total:
        print("✓ Todas las pruebas pasaron!")
        return 0
    else:
        print(f"✗ {total - passed} prueba(s) fallaron")
        return 1

if __name__ == '__main__':
    sys.exit(run_tests())
