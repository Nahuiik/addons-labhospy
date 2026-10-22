#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Stock Valuation Report
"""
import sys
import os

# Add Odoo to path
sys.path.insert(0, '/opt/odoo19')

try:
    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.tools import config
    
    # Parse config
    config.parse_config(['-c', '/dev/null'])
    
    # Get registry
    db_name = 'LAB19C'
    registry = odoo.registry(db_name)
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        print("=" * 60)
        print("STOCK VALUATION REPORT - FUNCTIONAL TEST")
        print("=" * 60)
        
        # 1. Check if stock_account module is installed
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
        
        # 2. Check if stock.valuation.layer model exists
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
            if hasattr(company, 'stock_value'):
                print("   ✓ Method stock_value exists")
                try:
                    test_data = company.stock_value()
                    print(f"   ✓ stock_value() returns: {len(test_data)} accounts")
                except Exception as e:
                    print(f"   ✗ Error calling stock_value(): {e}")
            else:
                print("   ✗ Method stock_value does NOT exist")
            
            if hasattr(company, 'stock_accounting_value'):
                print("   ✓ Method stock_accounting_value exists")
            else:
                print("   ✗ Method stock_accounting_value does NOT exist")
        else:
            print("   ✗ No company found")
        
        # 4. Check products
        print("\n4. Checking products...")
        products = env['product.product'].search([
            ('is_storable', '=', True),
            ('type', '=', 'product')
        ], limit=10)
        print(f"   ✓ Found {len(products)} storable products (showing first 10)")
        total_value = 0.0
        for p in products[:5]:
            value = p.total_value or 0.0
            total_value += value
            print(f"      - {p.name}: qty={p.qty_available}, value={value}")
        print(f"   ✓ Total value of first 5 products: {total_value}")
        
        # 5. Test report creation and computation
        print("\n5. Testing Stock Valuation Report...")
        if company:
            from odoo import fields
            from datetime import datetime, timedelta
            
            # Create report
            date_to = fields.Datetime.now()
            date_from = date_to - timedelta(days=30)
            
            report = env['stock.valuation.report'].create({
                'company_id': company.id,
                'date_from': date_from,
                'date_to': date_to,
            })
            print(f"   ✓ Report created: ID={report.id}")
            print(f"   ✓ Date range: {date_from.date()} to {date_to.date()}")
            
            # Compute valuation
            try:
                report._compute_valuation()
                print("   ✓ Computation successful")
                print(f"      Initial Balance: {report.initial_balance}")
                print(f"      Ending Stock: {report.ending_stock}")
                print(f"      Stock Variation: {report.stock_variation}")
                print(f"      Valuation Lines: {len(report.valuation_line_ids)}")
                
                if report.valuation_line_ids:
                    print("   ✓ Valuation lines:")
                    for line in report.valuation_line_ids[:5]:
                        print(f"      - {line.account_id.name if line.account_id else 'N/A'}: {line.value}")
            except Exception as e:
                print(f"   ✗ Error during computation: {e}")
                import traceback
                traceback.print_exc()
        
        # 6. Test action_compute
        print("\n6. Testing action_compute method...")
        if company and 'stock.valuation.report' in env:
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
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

