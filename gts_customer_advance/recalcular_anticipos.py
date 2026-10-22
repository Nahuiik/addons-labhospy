#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para recalcular anticipos disponibles en todas las facturas.
Ejecutar desde el shell de Odoo:
    python3 odoo-bin shell -d REALEZA
    >>> exec(open('/home/odoo/src/realeza/gts_customer_advance/recalcular_anticipos.py').read())
"""

# Recalcular anticipos disponibles en todas las facturas publicadas
invoices = env['account.move'].search([
    ('move_type', '=', 'out_invoice'),
    ('state', '=', 'posted'),
])

print(f'Facturas encontradas: {len(invoices)}')

if invoices:
    invoices._compute_has_available_advances()
    env.cr.commit()
    print('Recálculo completado')
    
    # Verificar resultados
    with_advances = invoices.filtered(lambda m: m.has_available_advances)
    print(f'Facturas con anticipos disponibles: {len(with_advances)}')
    for inv in with_advances[:10]:  # Mostrar primeras 10
        print(f'  - {inv.name}: {inv.available_advances_amount} ({inv.available_advances_count} anticipos)')
