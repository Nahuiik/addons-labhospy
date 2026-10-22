#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para recalcular advance_available_amount en todos los anticipos usando SQL directo.
IMPORTANTE: Ejecutar DESPUÉS de actualizar el módulo gts_customer_advance.

Ejecutar desde el shell de Odoo:
    python3 odoo-bin shell -d REALEZA
    >>> exec(open('/home/odoo/src/realeza/gts_customer_advance/recalcular_anticipos_disponibles.py').read())
"""

# Buscar anticipos usando SQL directo
env.cr.execute("""
    SELECT id, state, amount FROM account_payment WHERE is_advance = TRUE
""")
payments_data = env.cr.fetchall()

if not payments_data:
    print("No se encontraron anticipos")
else:
    print(f"Anticipos encontrados: {len(payments_data)}")
    print("Recalculando advance_available_amount usando SQL directo...")
    
    # Procesar cada anticipo
    updated_count = 0
    for payment_id, state, amount in payments_data:
        # Solo calcular para estados válidos: 'draft', 'in_process', 'paid'
        if state in ('draft', 'in_process', 'paid'):
            # Obtener aplicaciones usando SQL directo
            env.cr.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM account_advance_link
                WHERE payment_id = %s AND state = 'applied'
            """, (payment_id,))
            applied_amount = env.cr.fetchone()[0] or 0.0
            
            # Calcular saldo disponible
            available_amount = amount - applied_amount
            
            # Actualizar directamente en la base de datos
            env.cr.execute("""
                UPDATE account_payment
                SET advance_available_amount = %s,
                    advance_applied_total = %s
                WHERE id = %s
            """, (available_amount, applied_amount, payment_id))
            updated_count += 1
        else:
            # Para otros estados, establecer en 0
            env.cr.execute("""
                UPDATE account_payment
                SET advance_available_amount = 0.0,
                    advance_applied_total = 0.0
                WHERE id = %s
            """, (payment_id,))
    
    env.cr.commit()
    print(f'Recálculo completado. {updated_count} anticipos actualizados.')
    
    # Verificar resultados usando SQL
    env.cr.execute("""
        SELECT name, state, amount, advance_available_amount, advance_applied_total
        FROM account_payment
        WHERE is_advance = TRUE AND advance_available_amount > 0
        ORDER BY id
        LIMIT 10
    """)
    
    results = env.cr.fetchall()
    print(f'\nAnticipos con saldo disponible: {len(results)}')
    for row in results:
        print(f'  - {row[0]}: Estado={row[1]}, Monto={row[2]}, Disponible={row[3]}, Aplicado={row[4]}')
