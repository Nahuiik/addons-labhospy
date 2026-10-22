#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para Stock Valuation Report
Ejecutar desde la línea de comandos de Odoo
"""

import sys
sys.path.insert(0, '/opt/odoo19')

def diagnostico_completo():
    """Ejecuta diagnóstico completo del módulo"""
    try:
        import odoo
        from odoo import api, SUPERUSER_ID
        from odoo.tools import config
        from datetime import date, datetime
        
        config.parse_config(['-c', '/dev/null'])
        registry = odoo.registry('LAB19C')
        
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            
            print("=" * 80)
            print("DIAGNÓSTICO COMPLETO - STOCK VALUATION REPORT")
            print("=" * 80)
            
            # 1. Verificar módulo
            print("\n1. VERIFICACIÓN DEL MÓDULO")
            print("-" * 80)
            module = env['ir.module.module'].search([('name', '=', 'l10n_hn_stock_valuation')], limit=1)
            if module:
                print(f"✓ Módulo encontrado: {module.name}")
                print(f"  Estado: {module.state}")
                if module.state != 'installed':
                    print(f"  ⚠ PROBLEMA: El módulo NO está instalado (estado: {module.state})")
            else:
                print("✗ Módulo NO encontrado")
            
            # 2. Verificar modelo
            print("\n2. VERIFICACIÓN DEL MODELO")
            print("-" * 80)
            if 'stock.valuation.report' in env:
                print("✓ Modelo 'stock.valuation.report' está disponible")
                model = env['stock.valuation.report']
                print(f"  Tabla: {model._table}")
            else:
                print("✗ PROBLEMA: Modelo 'stock.valuation.report' NO está disponible")
                print("  → El módulo necesita ser actualizado/recargado")
                return
            
            # 3. Verificar dependencias
            print("\n3. VERIFICACIÓN DE DEPENDENCIAS")
            print("-" * 80)
            stock_account = env['ir.module.module'].search([('name', '=', 'stock_account')], limit=1)
            if stock_account and stock_account.state == 'installed':
                print("✓ stock_account está instalado")
            else:
                print("✗ PROBLEMA: stock_account NO está instalado")
            
            account = env['ir.module.module'].search([('name', '=', 'account')], limit=1)
            if account and account.state == 'installed':
                print("✓ account está instalado")
            else:
                print("✗ PROBLEMA: account NO está instalado")
            
            # 4. Verificar compañía
            print("\n4. VERIFICACIÓN DE COMPAÑÍA")
            print("-" * 80)
            company = env['res.company'].search([], limit=1)
            if company:
                print(f"✓ Compañía encontrada: {company.name} (ID: {company.id})")
            else:
                print("✗ PROBLEMA: No hay compañía configurada")
                return
            
            # 5. Verificar métodos de compañía
            print("\n5. VERIFICACIÓN DE MÉTODOS DE COMPAÑÍA")
            print("-" * 80)
            if hasattr(company, 'stock_value'):
                print("✓ Método stock_value() existe")
                try:
                    # Test con fecha actual
                    test_date = date.today()
                    test_data = company.stock_value(at_date=test_date)
                    total = sum(test_data.values()) if test_data else 0.0
                    print(f"✓ stock_value() funciona correctamente")
                    print(f"  Fecha de prueba: {test_date}")
                    print(f"  Total encontrado: {total}")
                    print(f"  Cuentas encontradas: {len(test_data)}")
                    if test_data:
                        for acc, val in list(test_data.items())[:3]:
                            print(f"    - {acc.name if acc else 'N/A'}: {val}")
                except Exception as e:
                    print(f"✗ PROBLEMA: Error al llamar stock_value(): {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("✗ PROBLEMA: Método stock_value() NO existe")
            
            # 6. Verificar productos
            print("\n6. VERIFICACIÓN DE PRODUCTOS")
            print("-" * 80)
            products = env['product.product'].search([
                ('is_storable', '=', True),
                ('type', '=', 'product')
            ])
            print(f"✓ Productos almacenables encontrados: {len(products)}")
            
            if len(products) > 0:
                # Verificar algunos productos
                print(f"\n  Primeros 5 productos:")
                total_value = 0.0
                for p in products[:5]:
                    value = p.total_value or 0.0
                    total_value += value
                    print(f"    - {p.name}: qty={p.qty_available}, value={value}")
                print(f"  Total valor (primeros 5): {total_value}")
                
                # Verificar cuentas de valuación
                print(f"\n  Verificando cuentas de valuación:")
                products_with_account = 0
                products_without_account = 0
                for p in products[:10]:
                    account = p.categ_id.property_stock_valuation_account_id
                    if account:
                        products_with_account += 1
                    else:
                        products_without_account += 1
                        print(f"    ⚠ {p.name}: Sin cuenta de valuación")
                print(f"  Con cuenta: {products_with_account}, Sin cuenta: {products_without_account}")
            else:
                print("  ⚠ ADVERTENCIA: No hay productos almacenables")
            
            # 7. Crear y probar reporte
            print("\n7. PRUEBA DE CREACIÓN DE REPORTE")
            print("-" * 80)
            try:
                date_to = env['ir.fields']._get_datetime(env['ir.fields']._get_datetime.now())
                date_from = date_to.replace(day=1) if date_to.day > 1 else date_to
                
                report = env['stock.valuation.report'].create({
                    'company_id': company.id,
                    'date_from': date_from,
                    'date_to': date_to,
                })
                print(f"✓ Reporte creado: ID={report.id}")
                print(f"  Company: {report.company_id.name}")
                print(f"  Date from: {report.date_from}")
                print(f"  Date to: {report.date_to}")
                
                # Verificar valores ANTES de calcular
                print(f"\n  Valores ANTES de _compute_valuation():")
                print(f"    initial_balance: {report.initial_balance}")
                print(f"    ending_stock: {report.ending_stock}")
                print(f"    stock_variation: {report.stock_variation}")
                print(f"    valuation_line_ids: {len(report.valuation_line_ids)}")
                
                # Forzar cálculo
                print(f"\n  Ejecutando _compute_valuation()...")
                report._compute_valuation()
                
                # Verificar valores DESPUÉS de calcular
                print(f"\n  Valores DESPUÉS de _compute_valuation():")
                print(f"    initial_balance: {report.initial_balance}")
                print(f"    ending_stock: {report.ending_stock}")
                print(f"    stock_variation: {report.stock_variation}")
                print(f"    valuation_line_ids: {len(report.valuation_line_ids)}")
                
                if report.valuation_line_ids:
                    print(f"\n  Líneas de valuación:")
                    for line in report.valuation_line_ids[:5]:
                        print(f"    - {line.account_id.name if line.account_id else 'N/A'}: value={line.value}")
                
                # Verificar si los campos están marcados como computed
                print(f"\n  Verificación de campos computed:")
                print(f"    initial_balance.compute: {report._fields['initial_balance'].compute}")
                print(f"    ending_stock.compute: {report._fields['ending_stock'].compute}")
                print(f"    stock_variation.compute: {report._fields['stock_variation'].compute}")
                
                # Test con fechas específicas (Nov 1-19, 2025)
                print(f"\n8. PRUEBA CON FECHAS ESPECÍFICAS (Nov 1-19, 2025)")
                print("-" * 80)
                from odoo import fields as odoo_fields
                date_from_test = odoo_fields.Datetime.combine(date(2025, 11, 1), datetime.min.time())
                date_to_test = odoo_fields.Datetime.combine(date(2025, 11, 19), datetime.max.time())
                
                report2 = env['stock.valuation.report'].create({
                    'company_id': company.id,
                    'date_from': date_from_test,
                    'date_to': date_to_test,
                })
                print(f"✓ Reporte creado para Nov 1-19, 2025")
                report2._compute_valuation()
                print(f"  initial_balance: {report2.initial_balance}")
                print(f"  ending_stock: {report2.ending_stock}")
                print(f"  stock_variation: {report2.stock_variation}")
                print(f"  valuation_line_ids: {len(report2.valuation_line_ids)}")
                
            except Exception as e:
                print(f"✗ ERROR al crear/probar reporte: {e}")
                import traceback
                traceback.print_exc()
            
            # 9. Verificar permisos
            print("\n9. VERIFICACIÓN DE PERMISOS")
            print("-" * 80)
            access = env['ir.model.access'].search([
                ('model_id.model', '=', 'stock.valuation.report'),
                ('group_id', '!=', False)
            ])
            if access:
                print(f"✓ Permisos encontrados: {len(access)}")
                for acc in access[:3]:
                    print(f"  - {acc.name}: read={acc.perm_read}, write={acc.perm_write}, create={acc.perm_create}")
            else:
                print("⚠ ADVERTENCIA: No se encontraron permisos específicos")
            
            # 10. Verificar vista
            print("\n10. VERIFICACIÓN DE VISTA")
            print("-" * 80)
            view = env['ir.ui.view'].search([
                ('model', '=', 'stock.valuation.report'),
                ('type', '=', 'form')
            ], limit=1)
            if view:
                print(f"✓ Vista encontrada: {view.name}")
            else:
                print("✗ PROBLEMA: Vista NO encontrada")
            
            # 11. Verificar acción y menú
            print("\n11. VERIFICACIÓN DE ACCIÓN Y MENÚ")
            print("-" * 80)
            action = env['ir.actions.act_window'].search([
                ('res_model', '=', 'stock.valuation.report')
            ], limit=1)
            if action:
                print(f"✓ Acción encontrada: {action.name}")
                print(f"  ID: {action.id}")
            else:
                print("✗ PROBLEMA: Acción NO encontrada")
            
            menu = env['ir.ui.menu'].search([
                ('action', '=', f'ir.actions.act_window,{action.id}' if action else False)
            ], limit=1)
            if menu:
                print(f"✓ Menú encontrado: {menu.name}")
            else:
                print("⚠ ADVERTENCIA: Menú NO encontrado")
            
            print("\n" + "=" * 80)
            print("DIAGNÓSTICO COMPLETADO")
            print("=" * 80)
            print("\nRECOMENDACIONES:")
            print("1. Si el módulo no está instalado, instálalo desde Aplicaciones")
            print("2. Si el modelo no está disponible, actualiza el módulo")
            print("3. Si stock_value() no funciona, verifica que stock_account esté instalado")
            print("4. Si no hay productos, verifica que haya productos almacenables")
            print("5. Si los valores son 0, verifica que haya movimientos de inventario")
            
    except Exception as e:
        print(f"ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    diagnostico_completo()

