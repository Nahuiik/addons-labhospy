# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestMonitorDevicePresence(TransactionCase):

    def setUp(self):
        super().setUp()
        self.presence_model = self.env['monitor.device_presence']
        self.user_model = self.env['res.users']
        
        # Crear un usuario de prueba
        self.test_user = self.user_model.create({
            'name': 'Usuario Prueba',
            'login': 'test_user_monitor',
            'email': 'test@example.com',
        })

    def test_register_heartbeat(self):
        """Test que se puede registrar un heartbeat"""
        device_id = 'test-device-123'
        
        # Registrar heartbeat
        presence = self.presence_model.register_heartbeat(
            device_id=device_id,
            user_id=self.test_user.id,
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        # Verificar que se creó
        self.assertTrue(presence)
        self.assertEqual(presence.device_id, device_id)
        self.assertEqual(presence.user_id.id, self.test_user.id)
        self.assertEqual(presence.ip_address, '127.0.0.1')
        
    def test_register_heartbeat_duplicate(self):
        """Test que no se pueden crear duplicados"""
        device_id = 'test-device-456'
        
        # Registrar primer heartbeat
        presence1 = self.presence_model.register_heartbeat(
            device_id=device_id,
            user_id=self.test_user.id
        )
        
        # Registrar segundo heartbeat (debería actualizar el existente)
        presence2 = self.presence_model.register_heartbeat(
            device_id=device_id,
            user_id=self.test_user.id
        )
        
        # Debería ser el mismo registro
        self.assertEqual(presence1.id, presence2.id)
        
    def test_get_user_type(self):
        """Test detección de tipo de usuario"""
        # Crear usuario portal
        portal_user = self.user_model.create({
            'name': 'Usuario Portal',
            'login': 'portal_test',
            'email': 'portal@example.com',
        })
        
        # Si tiene campo share, establecerlo
        if hasattr(portal_user, 'share'):
            portal_user.share = True
        
        # Registrar heartbeat
        presence = self.presence_model.register_heartbeat(
            device_id='portal-device',
            user_id=portal_user.id
        )
        
        # Verificar tipo (puede ser portal o internal dependiendo de la configuración)
        self.assertIn(presence.user_type, ['portal', 'internal'])
        
    def test_get_statistics(self):
        """Test obtención de estadísticas"""
        # Registrar algunos heartbeats
        self.presence_model.register_heartbeat(
            device_id='device1',
            user_id=self.test_user.id
        )
        
        # Obtener estadísticas
        stats = self.presence_model.get_statistics(window_minutes=60)
        
        # Verificar que retorna un dict con las claves esperadas
        self.assertIn('users_total', stats)
        self.assertIn('users_active', stats)
        self.assertIn('active_last_hour_total', stats)
        self.assertIn('active_users', stats)
        
    def test_get_active_users_last_hour(self):
        """Test obtención de usuarios activos última hora"""
        # Registrar heartbeat
        self.presence_model.register_heartbeat(
            device_id='active-device',
            user_id=self.test_user.id
        )
        
        # Obtener usuarios activos
        active_users = self.presence_model.get_active_users_last_hour(window_minutes=60)
        
        # Verificar estructura
        if active_users:
            user_data = active_users[0]
            self.assertIn('user_id', user_data)
            self.assertIn('login', user_data)
            self.assertIn('user_type', user_data)
            self.assertIn('devices_count', user_data)

    def test_inject_multiple_heartbeats(self):
        """Test para inyectar múltiples heartbeats de prueba"""
        import uuid
        
        # Registrar varios heartbeats para el mismo usuario
        device_ids = []
        for i in range(3):
            device_id = f'test-device-{uuid.uuid4()}'
            presence = self.presence_model.register_heartbeat(
                device_id=device_id,
                user_id=self.test_user.id,
                ip_address=f'192.168.1.{100+i}',
                user_agent=f'Test Device {i+1}'
            )
            device_ids.append(device_id)
        
        # Verificar que se crearon
        count = self.presence_model.search_count([('user_id', '=', self.test_user.id)])
        self.assertGreaterEqual(count, 3, "Debe haber al menos 3 registros")
        
        # Verificar usuarios activos
        active_users = self.presence_model.get_active_users_last_hour(window_minutes=60)
        self.assertGreater(len(active_users), 0, "Debe haber al menos un usuario activo")
        
        # Verificar que el usuario de prueba está en la lista
        test_user_found = any(u.get('user_id') == self.test_user.id for u in active_users)
        self.assertTrue(test_user_found, "El usuario de prueba debe estar en la lista de activos")

