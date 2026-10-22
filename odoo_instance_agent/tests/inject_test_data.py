# -*- coding: utf-8 -*-
"""
Script para inyectar datos de prueba directamente en la base de datos
"""
import sys
import os

# Agregar ruta de Odoo
sys.path.insert(0, '/opt/odoo19')

import odoo
from odoo import api, SUPERUSER_ID

def inject_test_data():
    """Inyecta datos de prueba directamente"""
    # Configurar Odoo
    odoo.tools.config.parse_config(['-d', 'LAB19C', '--stop-after-init'])
    
    # Inicializar Odoo
    registry = odoo.registry('LAB19C')
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
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
                user_agent='Test Script'
            )
            
            print(f"✅ Heartbeat registrado:")
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

