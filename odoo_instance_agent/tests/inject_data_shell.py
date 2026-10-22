#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para inyectar datos de prueba usando el shell de Odoo
Uso: python3 odoo-bin shell -d LAB19C < inject_data_shell.py
O ejecutar directamente con: python3 inject_data_shell.py
"""
import uuid
from datetime import datetime

# Registrar heartbeat directamente
device_id = str(uuid.uuid4())
admin_user = env['res.users'].search([('login', '=', 'admin')], limit=1)
if not admin_user:
    admin_user = env['res.users'].search([], limit=1)

if admin_user:
    presence_model = env['monitor.device_presence']
    presence = presence_model.register_heartbeat(
        device_id=device_id,
        user_id=admin_user.id,
        ip_address='127.0.0.1',
        user_agent='Test Script'
    )
    print(f"✅ Heartbeat registrado:")
    print(f"   - ID: {presence.id}")
    print(f"   - Device ID: {presence.device_id}")
    print(f"   - Usuario: {presence.user_id.name}")
    print(f"   - Last Seen: {presence.last_seen}")
    
    # Verificar
    count = presence_model.search_count([])
    print(f"\n✅ Total registros: {count}")
    
    active_users = presence_model.get_active_users_last_hour(window_minutes=60)
    print(f"✅ Usuarios activos: {len(active_users)}")
else:
    print("❌ No se encontró usuario")

