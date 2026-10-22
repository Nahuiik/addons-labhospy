# -*- coding: utf-8 -*-
"""
Test simple para inyectar datos - ejecutar con --test-tags
"""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
import uuid

@tagged('post_install', '-at_install')
class TestInjectData(TransactionCase):
    
    def test_inject_heartbeat_data(self):
        """Inyecta datos de prueba"""
        presence_model = self.env['monitor.device_presence']
        user_model = self.env['res.users']
        
        # Obtener usuario admin
        admin_user = user_model.search([('login', '=', 'admin')], limit=1)
        if not admin_user:
            admin_user = user_model.search([], limit=1)
        
        self.assertTrue(admin_user, "No se encontró usuario")
        
        # Registrar varios heartbeats
        device_ids = []
        for i in range(3):
            device_id = str(uuid.uuid4())
            presence = presence_model.register_heartbeat(
                device_id=device_id,
                user_id=admin_user.id,
                ip_address=f'192.168.1.{100+i}',
                user_agent=f'Test Device {i+1}'
            )
            device_ids.append(device_id)
            print(f"✅ Heartbeat {i+1} registrado: {device_id[:8]}...")
        
        # Verificar
        count = presence_model.search_count([])
        print(f"\n✅ Total registros: {count}")
        
        active_users = presence_model.get_active_users_last_hour(window_minutes=60)
        print(f"✅ Usuarios activos: {len(active_users)}")
        
        self.assertGreater(count, 0, "Debe haber al menos un registro")
        self.assertGreater(len(active_users), 0, "Debe haber al menos un usuario activo")

