
import json
import requests
import sys

# URL del servidor Odoo
BASE_URL = "http://127.0.0.1:8069"
DB = "odoo"
USER = "admin"
PASSWORD = "admin" 

def test_endpoints():
    session = requests.Session()
    
    # 1. Autenticación
    url_auth = f"{BASE_URL}/web/session/authenticate"
    auth_data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "db": DB,
            "login": USER,
            "password": PASSWORD
        }
    }
    
    try:
        print(f"Intentando conectar a {BASE_URL}...")
        r = session.post(url_auth, json=auth_data)
        
        if r.status_code != 200:
            print(f"Error HTTP en login: {r.status_code}")
            return
        
        res_json = r.json()
        if res_json.get("error"):
            print(f"Error Odoo Login: {res_json['error']}")
            # No retornamos, intentamos seguir por si la sesión es pública o auth falla pero endpoint es accesible (auth='user' requiere login)
        else:
            print("Login exitoso.")
        
        # 2. Test Receipt/Delivery Chart
        print("Testing /receipt/delivery/chart/data...")
        url_chart = f"{BASE_URL}/receipt/delivery/chart/data"
        payload = {
            'data': {
                'duration': 'all',
                'product_id': 'all',
                'warehouse_id': 'all'
            }
        }
        
        r_chart = session.post(url_chart, json=payload)
        print(f"Status Chart: {r_chart.status_code}")
        if r_chart.status_code == 200:
            try:
                data = r_chart.json()
                if 'receipt_delivery_chart_data' in data:
                     print("Chart Response OK: Datos recibidos correctamente.")
                else:
                     print(f"Chart Response Warning: JSON recibido pero sin clave esperada. {data.keys()}")
            except:
                print("Chart Response Error: No es JSON válido.")
        else:
            print(f"Chart Error 500/400: {r_chart.text[:200]}...")

        # 3. Test Inventory Table
        print("Testing /inventory/table/data...")
        url_table = f"{BASE_URL}/inventory/table/data"
        
        r_table = session.post(url_table, json=payload)
        print(f"Status Table: {r_table.status_code}")
        if r_table.status_code == 200:
            try:
                data = r_table.json()
                if 'top_product_selling_list' in data:
                    print("Table Response OK: Datos recibidos correctamente.")
                else:
                    print(f"Table Response Warning: JSON recibido pero sin clave esperada. {data.keys()}")
            except:
                 print("Table Response Error: No es JSON válido.")
        else:
            print(f"Table Error 500/400: {r_table.text[:200]}...")

    except Exception as e:
        print(f"Excepción durante el test: {e}")

if __name__ == "__main__":
    test_endpoints()




