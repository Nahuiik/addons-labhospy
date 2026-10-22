# -*- coding: utf-8 -*-
"""
Script de inyección de datos para probar el endpoint de heartbeat
"""
import requests
import json
import uuid

def test_heartbeat_endpoint():
    """Prueba el endpoint de heartbeat con datos reales"""
    url = 'http://localhost:8012/monitoring/heartbeat'
    
    # Generar device_id único
    device_id = str(uuid.uuid4())
    
    # Datos de prueba
    data = {
        'device_id': device_id,
        'user_id': 2  # Usuario admin por defecto
    }
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    print(f"Enviando heartbeat a {url}")
    print(f"Datos: {json.dumps(data, indent=2)}")
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        print(f"\nRespuesta HTTP: {response.status_code}")
        print(f"Respuesta JSON: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("\n✅ Heartbeat registrado exitosamente")
                return True
            else:
                print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"\n❌ Error HTTP: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False
    except Exception as e:
        print(f"\n❌ Excepción: {e}")
        return False

if __name__ == '__main__':
    test_heartbeat_endpoint()

