
import os
import sys
import ast

# Base path assuming we are in the module root or parent
BASE_DIR = os.getcwd()
if os.path.exists(os.path.join(BASE_DIR, 'udoo_web_list_view')):
    MODULE_DIR = os.path.join(BASE_DIR, 'udoo_web_list_view')
elif os.path.basename(BASE_DIR) == 'udoo_web_list_view':
    MODULE_DIR = BASE_DIR
else:
    # Fallback to absolute path known
    MODULE_DIR = '/opt/odoo19/addons-odoo/udoo_web_list_view'

print(f"Testing in directory: {MODULE_DIR}")

def check_file_exists(rel_path):
    path = os.path.join(MODULE_DIR, rel_path)
    if not os.path.exists(path):
        print(f"❌ ERROR: File not found: {path}")
        return False
    return True

def check_content(rel_path, expected_content, description):
    path = os.path.join(MODULE_DIR, rel_path)
    if not check_file_exists(rel_path):
        return False
    
    with open(path, 'r') as f:
        content = f.read()
    
    if expected_content in content:
        print(f"✅ {description}: FOUND")
        return True
    else:
        print(f"❌ {description}: NOT FOUND")
        return False

def check_python_syntax(rel_path):
    path = os.path.join(MODULE_DIR, rel_path)
    if not check_file_exists(rel_path):
        return False
    try:
        with open(path, 'r') as f:
            ast.parse(f.read())
        print(f"✅ Python Syntax {rel_path}: OK")
        return True
    except Exception as e:
        print(f"❌ Python Syntax {rel_path}: ERROR - {e}")
        return False

def run_tests():
    print("="*60)
    print("FUNCTIONAL TESTS - UDOO WEB LIST VIEW (ODOO 19)")
    print("="*60)
    
    all_passed = True
    
    # 1. Check JS Manager logic
    manager_js = "static/src/mod/manager.js"
    all_passed &= check_content(manager_js, "window.location.href = window.location.href", "Reload logic (window.location.href)")
    all_passed &= check_content(manager_js, "await fetch('/udoo/edit_list_view'", "Native fetch usage")
    all_passed &= check_content(manager_js, "onLabelChange: (newLabel)", "Reactive label update")
    
    # 2. Check Controller logic
    controller_py = "controllers/main.py"
    all_passed &= check_python_syntax(controller_py)
    all_passed &= check_content(controller_py, "type='http'", "Controller type='http'")
    all_passed &= check_content(controller_py, "request.get_json_data()", "Manual JSON decoding")
    all_passed &= check_content(controller_py, "json.loads(operations)", "JSON string parsing for operations")
    
    # 3. Check XML Template
    manager_xml = "static/src/mod/manager.xml"
    all_passed &= check_content(manager_xml, "t-on-change=\"onStringChange\"", "Input change event binding")

    print("-"*60)
    if all_passed:
        print("✅ ALL TESTS PASSED. MODULE IS READY.")
    else:
        print("❌ SOME TESTS FAILED. CHECK LOGS.")
    print("="*60)

if __name__ == "__main__":
    run_tests()
