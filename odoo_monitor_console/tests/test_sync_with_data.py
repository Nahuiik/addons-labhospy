# -*- coding: utf-8 -*-
"""
Test para sincronizar con datos reales
"""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
import uuid
from datetime import datetime, timedelta

@tagged('post_install', '-at_install')
class TestSyncWithData(TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.instance_model = self.env['monitor.instance']
        self.activity_line_model = self.env['monitor.user_activity_line']
        self.presence_model = self.env['monitor.device_presence']
        
        # Crear instancia de prueba
        self.instance = self.instance_model.create({
            'name': 'Test Instance',
            'url': 'http://localhost:8012',
            'active': True,
        })
        
        # Crear usuario de prueba y registrar heartbeat
        self.user = self.env['res.users'].search([('login', '=', 'admin')], limit=1)
        if not self.user:
            self.user = self.env['res.users'].search([], limit=1)
        
        # Registrar heartbeat directamente
        device_id = str(uuid.uuid4())
        self.presence_model.register_heartbeat(
            device_id=device_id,
            user_id=self.user.id,
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
    
    def test_sync_creates_activity_lines(self):
        """Test que la sincronización crea líneas de actividad"""
        # Simular datos de respuesta del endpoint
        from datetime import datetime
        now = datetime.now()
        
        data = {
            'instance': {
                'name': 'LAB19C',
                'version': '19.0',
                'db': 'LAB19C',
                'hostname': 'localhost'
            },
            'totals': {
                'users_total': 10,
                'users_active': 8,
                'users_archived': 2,
                'portal_total': 3,
                'internal_total': 5
            },
            'active_last_hour': {
                'total': 2,
                'portal': 1,
                'internal': 1
            },
            'active_users': [
                {
                    'user_id': self.user.id,
                    'login': self.user.login,
                    'name': self.user.name,
                    'user_type': 'internal',
                    'archived': False,
                    'last_activity': now.isoformat(),
                    'devices_count': 1,
                }
            ]
        }
        
        # Crear líneas de actividad
        self.instance._create_activity_lines(data)
        
        # Verificar que se crearon
        activity_lines = self.activity_line_model.search([
            ('instance_id', '=', self.instance.id)
        ])
        
        self.assertGreater(len(activity_lines), 0, "Debe haber al menos una línea de actividad")
        self.assertEqual(activity_lines[0].user_login, self.user.login)
        self.assertEqual(activity_lines[0].devices_count, 1)
        
        print(f"\n✅ Líneas de actividad creadas: {len(activity_lines)}")
        for line in activity_lines:
            print(f"   - {line.user_login}: {line.devices_count} dispositivos, última actividad: {line.last_activity}")

