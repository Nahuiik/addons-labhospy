#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script SQL directo para recalcular advance_available_amount.
Ejecutar desde el shell de Odoo DESPUÉS de actualizar el módulo:
    python3 odoo-bin shell -d REALEZA
    >>> exec(open('/home/odoo/src/realeza/gts_customer_advance/recalcular_anticipos_sql.py').read())
"""

# Primero asegurarse de que el módulo esté cargado
env['ir.module.module'].update_list()
module = env['ir.module.module'].search([('name', '=', 'gts_customer_advance')])
if module.state != 'installed':
    print(f"El módulo gts_customer_advance no está instalado. Estado: {module.state}")
else:
    print("Módulo gts_customer_advance está instalado")
    
    # Buscar anticipos usando SQL directo para evitar problemas con campos computed
    env.cr.execute("""
        SELECT id, name, state, amount, is_advance
        FROM account_payment
        WHERE is_advance = TRUE
        ORDER BY id
    """)
    
    payments_data = env.cr.fetchall()
    print(f"Anticipos encontrados: {len(payments_data)}")
    
    if payments_data:
        Payment = env['account.payment']
        payments = Payment.browse([row[0] for row in payments_data])
        
        print("Recalculando advance_available_amount...")
        # Invalidar el campo para forzar recálculo
        payments.invalidate_recordset(['advance_available_amount', 'advance_applied_total'])
        # Recalcular
        payments._compute_advance_available_amount()
        env.cr.commit()
        print("Recálculo completado")
        
        # Verificar resultados usando SQL
        env.cr.execute("""
            SELECT name, state, amount, advance_available_amount, advance_applied_total
            FROM account_payment
            WHERE is_advance = TRUE AND advance_available_amount > 0
            ORDER BY id
            LIMIT 10
        """)
        
        results = env.cr.fetchall()
        print(f"\nAnticipos con saldo disponible: {len(results)}")
        for row in results:
            print(f"  - {row[0]}: Estado={row[1]}, Monto={row[2]}, Disponible={row[3]}, Aplicado={row[4]}")
