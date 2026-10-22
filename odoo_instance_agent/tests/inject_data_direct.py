#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para inyectar datos de prueba directamente usando el framework de Odoo
Ejecutar: python3 odoo-bin -d LAB19C --addons-path=/opt/odoo19/odoo/addons,/opt/odoo19/addons-odoo --test-tags=odoo_instance_agent --stop-after-init
O mejor: usar el script de abajo
"""
import sys
import os

# Agregar ruta de Odoo
sys.path.insert(0, '/opt/odoo19')

# Configurar Odoo antes de importar
os.environ.setdefault('ODOO_RC', '/home/odoo/.odoorc')

import odoo
from odoo import api, SUPERUSER_ID

def inject_test_data():
    """Inyecta datos de prueba directamente"""
    # Configurar Odoo
    odoo.tools.config.parse_config([
        '-d', 'LAB19C',
        '--addons-path=/opt/odoo19/odoo/addons,/opt/odoo19/addons-odoo',
        '--stop-after-init'
    ])
    
    # Inicializar Odoo
    odoo.service.db.init()
    registry = odoo.registry('LAB19C')
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # Verificar que el módulo esté instalado
        module = env['ir.module.module'].search([('name', '=', 'odoo_instance_agent')], limit=1)
        if not module or module.state != 'installed':
            print("❌ El módulo odoo_instance_agent no está instalado")
            print(f"   Estado: {module.state if module else 'No encontrado'}")
            return False
        
        print("✅ Módulo odoo_instance_agent está instalado")
        
        # Obtener modelo
        presence_model = env['monitor.device_presence']
        user_model = env['res.users']
        
        # Obtener usuario admin
        admin_user = user_model.search([('login', '=', 'admin')], limit=1)
        if not admin_user:
            admin_user = user_model.search([], limit=1)
        
        if not admin_user:
            print("❌ No se encontró ningún usuario")
            return False
        
        print(f"✅ Usuario encontrado: {admin_user.login} (ID: {admin_user.id})")
        
        # Registrar heartbeat directamente
        import uuid
        device_id = str(uuid.uuid4())
        
        try:
            presence = presence_model.register_heartbeat(
                device_id=device_id,
                user_id=admin_user.id,
                ip_address='127.0.0.1',
                user_agent='Test Script Direct'
            )
            
            print(f"\n✅ Heartbeat registrado:")
            print(f"   - ID: {presence.id}")
            print(f"   - Device ID: {presence.device_id}")
            print(f"   - Usuario: {presence.user_id.name}")
            print(f"   - Last Seen: {presence.last_seen}")
            print(f"   - User Type: {presence.user_type}")
            
            # Verificar que se guardó
            count = presence_model.search_count([])
            print(f"\n✅ Total de registros en BD: {count}")
            
            # Obtener usuarios activos
            active_users = presence_model.get_active_users_last_hour(window_minutes=60)
            print(f"✅ Usuarios activos última hora: {len(active_users)}")
            
            if active_users:
                for user_data in active_users:
                    print(f"   - {user_data.get('login')}: {user_data.get('devices_count')} dispositivos")
            
            cr.commit()
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            cr.rollback()
            return False

if __name__ == '__main__':
    success = inject_test_data()
    sys.exit(0 if success else 1)

