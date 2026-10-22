# -*- coding: utf-8 -*-

import logging
from unittest.mock import Mock, patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TestMonitorInstance(TransactionCase):
    """Pruebas funcionales para monitor.instance"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.MonitorInstance = cls.env['monitor.instance']
        cls.MonitorUserSnapshot = cls.env['monitor.user_snapshot']
        cls.MonitorUserActivityLine = cls.env['monitor.user_activity_line']

    def test_create_instance(self):
        """Test: Crear una instancia de monitoreo"""
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'test_token_123',
            'active': True,
            'sync_interval': 5,
        })
        
        self.assertEqual(instance.name, 'Test Instance')
        self.assertEqual(instance.url, 'http://test.example.com:8069')
        self.assertEqual(instance.token, 'test_token_123')
        self.assertTrue(instance.active)
        self.assertEqual(instance.sync_interval, 5)
        self.assertEqual(instance.last_sync_status, 'never')

    def test_unique_url_constraint(self):
        """Test: No se pueden crear dos instancias con la misma URL"""
        self.MonitorInstance.create({
            'name': 'Instance 1',
            'url': 'http://test.example.com:8069',
            'token': 'token1',
        })
        
        with self.assertRaises(Exception):  # ValidationError o IntegrityError
            self.MonitorInstance.create({
                'name': 'Instance 2',
                'url': 'http://test.example.com:8069',  # Misma URL
                'token': 'token2',
            })

    def test_compute_is_online(self):
        """Test: Cálculo de estado online"""
        from datetime import timedelta
        from odoo import fields
        
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'test_token',
            'sync_interval': 5,
        })
        
        # Inicialmente no está online
        self.assertFalse(instance.is_online)
        
        # Marcar como sincronizado exitosamente hace poco tiempo
        instance.write({
            'last_sync': fields.Datetime.now() - timedelta(minutes=2),
            'last_sync_status': 'success',
        })
        instance._compute_is_online()
        self.assertTrue(instance.is_online)
        
        # Si fue hace mucho tiempo, no está online
        instance.write({
            'last_sync': fields.Datetime.now() - timedelta(minutes=20),
            'last_sync_status': 'success',
        })
        instance._compute_is_online()
        self.assertFalse(instance.is_online)

    @patch('requests.get')
    def test_sync_instance_success(self, mock_get):
        """Test: Sincronización exitosa de instancia"""
        # Mock de respuesta exitosa
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'instance': {
                'name': 'Test DB',
                'version': '19.0',
                'db': 'test_db',
                'hostname': 'test-host',
                'timestamp': '2025-12-14T20:00:00',
            },
            'window_minutes': 60,
            'totals': {
                'users_total': 100,
                'users_active': 80,
                'users_archived': 20,
                'portal_total': 30,
                'internal_total': 50,
            },
            'active_last_hour': {
                'total': 25,
                'portal': 10,
                'internal': 15,
            },
            'active_users': [
                {
                    'login': 'user1',
                    'name': 'User One',
                    'user_type': 'internal',
                    'archived': False,
                    'last_activity': '2025-12-14T19:30:00',
                    'devices_count': 2,
                }
            ],
        }
        mock_get.return_value = mock_response
        
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'test_token',
            'active': True,
        })
        
        result = instance.sync_instance()
        
        self.assertTrue(result['success'])
        self.assertEqual(instance.version, '19.0')
        self.assertEqual(instance.db_name, 'test_db')
        self.assertEqual(instance.hostname, 'test-host')
        self.assertEqual(instance.last_sync_status, 'success')
        
        # Verificar que se creó un snapshot
        snapshots = self.MonitorUserSnapshot.search([
            ('instance_id', '=', instance.id)
        ])
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots.users_total, 100)
        self.assertEqual(snapshots.active_last_hour_total, 25)
        
        # Verificar que se crearon líneas de actividad
        activity_lines = self.MonitorUserActivityLine.search([
            ('instance_id', '=', instance.id)
        ])
        self.assertEqual(len(activity_lines), 1)
        self.assertEqual(activity_lines.user_login, 'user1')

    @patch('requests.get')
    def test_sync_instance_error(self, mock_get):
        """Test: Manejo de errores en sincronización"""
        # Mock de respuesta con error
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = 'Forbidden'
        mock_get.return_value = mock_response
        
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'wrong_token',
            'active': True,
        })
        
        result = instance.sync_instance()
        
        self.assertFalse(result['success'])
        self.assertEqual(instance.last_sync_status, 'error')
        self.assertIn('HTTP 403', instance.last_sync_error)

    @patch('requests.get')
    def test_sync_instance_timeout(self, mock_get):
        """Test: Manejo de timeout en sincronización"""
        import requests
        
        mock_get.side_effect = requests.exceptions.Timeout('Connection timeout')
        
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'test_token',
            'active': True,
        })
        
        result = instance.sync_instance()
        
        self.assertFalse(result['success'])
        self.assertEqual(instance.last_sync_status, 'error')
        self.assertIn('Timeout', instance.last_sync_error)

    def test_sync_inactive_instance(self):
        """Test: No sincronizar instancias inactivas"""
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'test_token',
            'active': False,
        })
        
        result = instance.sync_instance()
        
        self.assertFalse(result['success'])
        self.assertIn('inactiva', result['error'].lower())

    def test_create_snapshot(self):
        """Test: Creación de snapshot"""
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'test_token',
        })
        
        data = {
            'totals': {
                'users_total': 100,
                'users_active': 80,
                'users_archived': 20,
                'portal_total': 30,
                'internal_total': 50,
            },
            'active_last_hour': {
                'total': 25,
                'portal': 10,
                'internal': 15,
            },
            'instance': {
                'version': '19.0',
                'db': 'test_db',
            },
        }
        
        snapshot = instance._create_snapshot(data)
        
        self.assertEqual(snapshot.instance_id, instance)
        self.assertEqual(snapshot.users_total, 100)
        self.assertEqual(snapshot.active_last_hour_total, 25)
        self.assertEqual(snapshot.instance_version, '19.0')

    def test_create_activity_lines(self):
        """Test: Creación de líneas de actividad"""
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'test_token',
        })
        
        from datetime import datetime
        
        data = {
            'active_users': [
                {
                    'login': 'user1',
                    'name': 'User One',
                    'user_type': 'internal',
                    'archived': False,
                    'last_activity': '2025-12-14T19:30:00',
                    'devices_count': 2,
                },
                {
                    'login': 'user2',
                    'name': 'User Two',
                    'user_type': 'portal',
                    'archived': False,
                    'last_activity': '2025-12-14T19:45:00',
                    'devices_count': 1,
                },
            ],
        }
        
        instance._create_activity_lines(data)
        
        activity_lines = self.MonitorUserActivityLine.search([
            ('instance_id', '=', instance.id)
        ])
        
        self.assertEqual(len(activity_lines), 2)
        self.assertEqual(activity_lines[0].user_login, 'user2')  # Ordenado por last_activity desc
        self.assertEqual(activity_lines[1].user_login, 'user1')

    def test_get_consolidated_active_users(self):
        """Test: Obtener usuarios activos consolidados"""
        instance1 = self.MonitorInstance.create({
            'name': 'Instance 1',
            'url': 'http://test1.example.com:8069',
            'token': 'token1',
        })
        
        instance2 = self.MonitorInstance.create({
            'name': 'Instance 2',
            'url': 'http://test2.example.com:8069',
            'token': 'token2',
        })
        
        from datetime import datetime, timedelta
        from odoo import fields
        
        # Crear líneas de actividad para el mismo usuario en diferentes instancias
        self.MonitorUserActivityLine.create({
            'instance_id': instance1.id,
            'user_login': 'user1',
            'user_name': 'User One',
            'user_type': 'internal',
            'last_activity': fields.Datetime.now() - timedelta(minutes=30),
            'devices_count': 2,
        })
        
        self.MonitorUserActivityLine.create({
            'instance_id': instance2.id,
            'user_login': 'user1',
            'user_name': 'User One',
            'user_type': 'internal',
            'last_activity': fields.Datetime.now() - timedelta(minutes=20),
            'devices_count': 1,
        })
        
        consolidated = self.MonitorUserActivityLine.get_consolidated_active_users()
        
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0]['login'], 'user1')
        self.assertEqual(consolidated[0]['total_devices'], 3)  # 2 + 1
        self.assertEqual(len(consolidated[0]['instances']), 2)

    def test_get_top_users_by_devices(self):
        """Test: Obtener ranking de usuarios por dispositivos"""
        instance = self.MonitorInstance.create({
            'name': 'Test Instance',
            'url': 'http://test.example.com:8069',
            'token': 'test_token',
        })
        
        from datetime import timedelta
        from odoo import fields
        
        # Crear usuarios con diferentes números de dispositivos
        self.MonitorUserActivityLine.create({
            'instance_id': instance.id,
            'user_login': 'user1',
            'user_name': 'User One',
            'user_type': 'internal',
            'last_activity': fields.Datetime.now() - timedelta(minutes=30),
            'devices_count': 5,
        })
        
        self.MonitorUserActivityLine.create({
            'instance_id': instance.id,
            'user_login': 'user2',
            'user_name': 'User Two',
            'user_type': 'portal',
            'last_activity': fields.Datetime.now() - timedelta(minutes=20),
            'devices_count': 3,
        })
        
        self.MonitorUserActivityLine.create({
            'instance_id': instance.id,
            'user_login': 'user3',
            'user_name': 'User Three',
            'user_type': 'internal',
            'last_activity': fields.Datetime.now() - timedelta(minutes=10),
            'devices_count': 1,
        })
        
        top_users = self.MonitorUserActivityLine.get_top_users_by_devices(limit=2)
        
        self.assertEqual(len(top_users), 2)
        self.assertEqual(top_users[0]['login'], 'user1')  # 5 dispositivos
        self.assertEqual(top_users[1]['login'], 'user2')  # 3 dispositivos

