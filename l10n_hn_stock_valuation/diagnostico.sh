#!/bin/bash
# Script de diagnóstico para Stock Valuation Report

cd /opt/odoo19

python3 odoo/odoo-bin shell -d LAB19C --no-http << 'PYTHON'
print("=" * 80)
print("DIAGNÓSTICO COMPLETO - STOCK VALUATION REPORT")
print("=" * 80)

# 1. Verificar módulo
print("\n1. VERIFICACIÓN DEL MÓDULO")
print("-" * 80)
module = env['ir.module.module'].search([('name', '=', 'deltatech_stock_inventory')], limit=1)
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
    print("\n  SOLUCIÓN: Actualiza el módulo desde Aplicaciones > deltatech_stock_inventory > Actualizar")
    exit()

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
    exit()

# 5. Verificar métodos de compañía
print("\n5. VERIFICACIÓN DE MÉTODOS DE COMPAÑÍA")
print("-" * 80)
if hasattr(company, 'stock_value'):
    print("✓ Método stock_value() existe")
    try:
        from datetime import date
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
            if products_without_account <= 3:
                print(f"    ⚠ {p.name}: Sin cuenta de valuación")
    print(f"  Con cuenta: {products_with_account}, Sin cuenta: {products_without_account}")
else:
    print("  ⚠ ADVERTENCIA: No hay productos almacenables")

# 7. Crear y probar reporte
print("\n7. PRUEBA DE CREACIÓN DE REPORTE")
print("-" * 80)
try:
    from odoo import fields
    from datetime import datetime, date
    
    date_to = fields.Datetime.now()
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
        print(f"\n  Líneas de valuación (primeras 5):")
        for line in report.valuation_line_ids[:5]:
            print(f"    - {line.account_id.name if line.account_id else 'N/A'}: value={line.value}, debit={line.debit}, credit={line.credit}")
    else:
        print(f"\n  ⚠ ADVERTENCIA: No se crearon líneas de valuación")
    
    # Test con fechas específicas (Nov 1-19, 2025)
    print(f"\n8. PRUEBA CON FECHAS ESPECÍFICAS (Nov 1-19, 2025)")
    print("-" * 80)
    date_from_test = fields.Datetime.combine(date(2025, 11, 1), datetime.min.time())
    date_to_test = fields.Datetime.combine(date(2025, 11, 19), datetime.max.time())
    
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
    
    if report2.valuation_line_ids:
        print(f"\n  Líneas de valuación:")
        for line in report2.valuation_line_ids[:5]:
            print(f"    - {line.account_id.name if line.account_id else 'N/A'}: value={line.value}")
    
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

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)
print("\nRECOMENDACIONES:")
print("1. Si el módulo no está instalado, instálalo desde Aplicaciones")
print("2. Si el modelo no está disponible, actualiza el módulo")
print("3. Si stock_value() no funciona, verifica que stock_account esté instalado")
print("4. Si no hay productos, verifica que haya productos almacenables")
print("5. Si los valores son 0, verifica que haya movimientos de inventario")
print("6. Si ending_stock es 0 pero stock_value() devuelve datos, hay un problema en _compute_valuation()")
PYTHON

