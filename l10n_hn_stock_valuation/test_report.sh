#!/bin/bash
# Test script for Stock Valuation Report

cd /opt/odoo19

python3 odoo/odoo-bin shell -d LAB19C --no-http << 'PYTHON'
print("=" * 60)
print("STOCK VALUATION REPORT - FUNCTIONAL TEST")
print("=" * 60)

# 1. Check stock_account module
print("\n1. Checking stock_account module...")
module = env['ir.module.module'].search([('name', '=', 'stock_account')], limit=1)
if module:
    print(f"   ✓ Module found: state={module.state}")
    if module.state == 'installed':
        print("   ✓ Module is INSTALLED")
    else:
        print(f"   ✗ Module is NOT installed (state: {module.state})")
else:
    print("   ✗ Module stock_account not found")

# 2. Check stock.valuation.layer model
print("\n2. Checking stock.valuation.layer model...")
if 'stock.valuation.layer' in env:
    print("   ✓ Model stock.valuation.layer is available")
    svl_count = env['stock.valuation.layer'].search_count([])
    print(f"   ✓ Total SVLs in database: {svl_count}")
else:
    print("   ✗ Model stock.valuation.layer is NOT available")

# 3. Check company methods
print("\n3. Checking company methods...")
company = env['res.company'].search([], limit=1)
if company:
    print(f"   ✓ Company found: {company.name}")
    print(f"   ✓ Has stock_value: {hasattr(company, 'stock_value')}")
    print(f"   ✓ Has stock_accounting_value: {hasattr(company, 'stock_accounting_value')}")
    if hasattr(company, 'stock_value'):
        try:
            test_data = company.stock_value()
            print(f"   ✓ stock_value() returns: {len(test_data)} accounts")
            if test_data:
                for acc, val in list(test_data.items())[:3]:
                    print(f"      - {acc.name if acc else 'N/A'}: {val}")
        except Exception as e:
            print(f"   ✗ Error calling stock_value(): {e}")
else:
    print("   ✗ No company found")

# 4. Check products
print("\n4. Checking products...")
products = env['product.product'].search([
    ('is_storable', '=', True),
    ('type', '=', 'product')
], limit=10)
print(f"   ✓ Found {len(products)} storable products")
total_value = 0.0
for p in products[:5]:
    value = p.total_value or 0.0
    total_value += value
    print(f"      - {p.name}: qty={p.qty_available}, value={value}")
print(f"   ✓ Total value of first 5 products: {total_value}")

# 5. Test report creation
print("\n5. Testing Stock Valuation Report...")
if company:
    from odoo import fields
    from datetime import timedelta
    
    date_to = fields.Datetime.now()
    date_from = date_to - timedelta(days=30)
    
    report = env['stock.valuation.report'].create({
        'company_id': company.id,
        'date_from': date_from,
        'date_to': date_to,
    })
    print(f"   ✓ Report created: ID={report.id}")
    print(f"   ✓ Date range: {date_from.date()} to {date_to.date()}")
    
    try:
        report._compute_valuation()
        print("   ✓ Computation successful")
        print(f"      Initial Balance: {report.initial_balance}")
        print(f"      Ending Stock: {report.ending_stock}")
        print(f"      Stock Variation: {report.stock_variation}")
        print(f"      Valuation Lines: {len(report.valuation_line_ids)}")
        
        if report.valuation_line_ids:
            print("   ✓ Valuation lines (first 5):")
            for line in report.valuation_line_ids[:5]:
                print(f"      - {line.account_id.name if line.account_id else 'N/A'}: {line.value}")
    except Exception as e:
        print(f"   ✗ Error during computation: {e}")
        import traceback
        traceback.print_exc()

# 6. Test action_compute
print("\n6. Testing action_compute method...")
if company:
    try:
        report = env['stock.valuation.report'].create({
            'company_id': company.id,
            'date_to': fields.Datetime.now(),
        })
        result = report.action_compute()
        print("   ✓ action_compute() executed successfully")
        print(f"   ✓ Return type: {result.get('type')}")
    except Exception as e:
        print(f"   ✗ Error in action_compute(): {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETED")
print("=" * 60)
PYTHON

