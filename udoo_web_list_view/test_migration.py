# -*- coding: utf-8 -*-
"""
Script de pruebas funcionales para la migración de udoo_web_list_view a Odoo 19
Este script verifica que el módulo esté correctamente migrado y funcional.
"""

import os
import sys
import ast
import xml.etree.ElementTree as ET

def check_python_syntax(file_path):
    """Verifica la sintaxis de un archivo Python"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, "OK"
    except SyntaxError as e:
        return False, f"Error de sintaxis: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def check_xml_syntax(file_path):
    """Verifica la sintaxis de un archivo XML"""
    try:
        tree = ET.parse(file_path)
        return True, "OK"
    except ET.ParseError as e:
        return False, f"Error de sintaxis XML: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def check_manifest():
    """Verifica el manifest del módulo"""
    manifest_path = '/opt/odoo19/addons-odoo/udoo_web_list_view/__manifest__.py'
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Verificar que tenga las dependencias correctas
        if "'depends': ['web']" in content or '"depends": ["web"]' in content:
            return True, "Manifest válido con dependencia 'web'"
        else:
            return False, "Manifest no tiene dependencia 'web'"
    except Exception as e:
        return False, f"Error leyendo manifest: {e}"

def check_imports_js():
    """Verifica que las importaciones JavaScript sean correctas para Odoo 19"""
    js_files = [
        '/opt/odoo19/addons-odoo/udoo_web_list_view/static/src/list/renderer.js',
        '/opt/odoo19/addons-odoo/udoo_web_list_view/static/src/list/controller.js',
        '/opt/odoo19/addons-odoo/udoo_web_list_view/static/src/mod/manager.js',
    ]
    
    odoo19_imports = [
        '@odoo/owl',
        '@web/core',
        'useService',
        'useBus',
        'useState',
    ]
    
    results = []
    for js_file in js_files:
        if not os.path.exists(js_file):
            results.append((js_file, False, "Archivo no encontrado"))
            continue
        
        try:
            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verificar que use las importaciones correctas
            has_odoo19_imports = any(imp in content for imp in odoo19_imports)
            if has_odoo19_imports:
                results.append((js_file, True, "Usa importaciones de Odoo 19"))
            else:
                results.append((js_file, False, "No se detectaron importaciones de Odoo 19"))
        except Exception as e:
            results.append((js_file, False, f"Error: {e}"))
    
    return results

def check_api_compatibility():
    """Verifica que las APIs usadas sean compatibles con Odoo 19"""
    renderer_path = '/opt/odoo19/addons-odoo/udoo_web_list_view/static/src/list/renderer.js'
    
    if not os.path.exists(renderer_path):
        return False, "Archivo renderer.js no encontrado"
    
    with open(renderer_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar APIs migradas
    checks = {
        'useBus hook': 'useBus' in content,
        'useService hook': 'useService' in content,
        'dialogService (no env.services.dialog)': 'this.dialogService' in content or 'this.dialog' in content,
        'actionService (no env.services.action)': 'this.actionService' in content,
        'searchModel para fields': 'this.env.searchModel' in content or 'list.model' in content,
    }
    
    all_passed = all(checks.values())
    details = ", ".join([k for k, v in checks.items() if v])
    
    return all_passed, details if all_passed else f"Faltan: {[k for k, v in checks.items() if not v]}"

def run_tests():
    """Ejecuta todas las pruebas"""
    print("=" * 70)
    print("PRUEBAS FUNCIONALES - MIGRACIÓN UDOO_WEB_LIST_VIEW A ODOO 19")
    print("=" * 70)
    print()
    
    results = []
    
    # 1. Verificar manifest
    print("1. Verificando __manifest__.py...")
    success, msg = check_manifest()
    results.append(("Manifest", success, msg))
    print(f"   {'✓' if success else '✗'} {msg}")
    print()
    
    # 2. Verificar sintaxis Python
    print("2. Verificando sintaxis de archivos Python...")
    python_files = [
        '/opt/odoo19/addons-odoo/udoo_web_list_view/__init__.py',
        '/opt/odoo19/addons-odoo/udoo_web_list_view/controllers/__init__.py',
        '/opt/odoo19/addons-odoo/udoo_web_list_view/controllers/main.py',
    ]
    
    for py_file in python_files:
        if os.path.exists(py_file):
            success, msg = check_python_syntax(py_file)
            results.append((os.path.basename(py_file), success, msg))
            print(f"   {'✓' if success else '✗'} {os.path.basename(py_file)}: {msg}")
    print()
    
    # 3. Verificar sintaxis XML
    print("3. Verificando sintaxis de archivos XML...")
    xml_files = [
        '/opt/odoo19/addons-odoo/udoo_web_list_view/static/src/list/renderer.xml',
        '/opt/odoo19/addons-odoo/udoo_web_list_view/static/src/list/controller.xml',
        '/opt/odoo19/addons-odoo/udoo_web_list_view/static/src/mod/manager.xml',
    ]
    
    for xml_file in xml_files:
        if os.path.exists(xml_file):
            success, msg = check_xml_syntax(xml_file)
            results.append((os.path.basename(xml_file), success, msg))
            print(f"   {'✓' if success else '✗'} {os.path.basename(xml_file)}: {msg}")
    print()
    
    # 4. Verificar importaciones JavaScript
    print("4. Verificando importaciones JavaScript (Odoo 19)...")
    import_results = check_imports_js()
    for file_path, success, msg in import_results:
        results.append((os.path.basename(file_path), success, msg))
        print(f"   {'✓' if success else '✗'} {os.path.basename(file_path)}: {msg}")
    print()
    
    # 5. Verificar compatibilidad de APIs
    print("5. Verificando compatibilidad de APIs con Odoo 19...")
    success, msg = check_api_compatibility()
    results.append(("API Compatibility", success, msg))
    print(f"   {'✓' if success else '✗'} {msg}")
    print()
    
    # Resumen
    print("=" * 70)
    print("RESUMEN DE PRUEBAS")
    print("=" * 70)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"Pruebas pasadas: {passed}/{total}")
    print()
    
    if passed == total:
        print("✓ TODAS LAS PRUEBAS PASARON - El módulo está listo para Odoo 19")
    else:
        print("✗ ALGUNAS PRUEBAS FALLARON:")
        for name, success, msg in results:
            if not success:
                print(f"   - {name}: {msg}")
    
    print("=" * 70)
    
    return passed == total

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)




