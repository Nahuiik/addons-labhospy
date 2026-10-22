# -*- coding: utf-8 -*-
"""
Script de diagnóstico: validar cálculo ISR para un empleado (incl. proyección por fecha de ingreso).

Ejecutar en shell de Odoo:
  odoo-bin shell -d GRUPOHMM
  >>> employee_name = "Empleado de prueba 1002"
  >>> exec(open('addons/l10n_hn_hr_payroll/scripts/diagnostico_isr_empleado.py').read())

O con employee_id:
  >>> employee_id = 123
  >>> exec(open('addons/l10n_hn_hr_payroll/scripts/diagnostico_isr_empleado.py').read())
"""
from datetime import date

env = globals().get('env')
if not env:
    print("Ejecutar dentro del shell de Odoo")
    raise SystemExit(1)

employee_name = globals().get('employee_name', 'Empleado de prueba 1002')
employee_id = globals().get('employee_id')

Employee = env['hr.employee']
if employee_id:
    employees = Employee.browse([employee_id] if isinstance(employee_id, int) else employee_id)
else:
    employees = Employee.search([('name', 'ilike', employee_name)])

if not employees:
    print(f"No se encontró empleado con nombre similar a '{employee_name}'")
    raise SystemExit(0)

year = date.today().year
Config = env['l10n.hn.isr.config']
Payslip = env['hr.payslip']
Audit = env['l10n.hn.isr.audit']

config = Config.search([
    ('year', '=', year),
    ('company_id', '=', env.company.id),
    ('state', '=', 'validated'),
    ('active', '=', True),
], limit=1)

if not config:
    print(f"No hay configuración ISR validada para año {year}")
    raise SystemExit(0)

for emp in employees:
    print("\n" + "=" * 70)
    print(f"EMPLEADO: {emp.name} (ID: {emp.id})")
    print("=" * 70)

    version = emp.current_version_id
    if not version:
        print("  ❌ No tiene contrato activo (current_version_id)")
        continue

    hire_date = config._get_hire_date_for_year(emp, year)
    contract_start = version.contract_date_start

    print("\n--- 1. FECHA DE INGRESO ---")
    print(f"  contract_date_start (versión actual): {contract_start}")
    print(f"  hire_date para año {year} (ajuste mid-year): {hire_date or 'None (año completo)'}")
    if hire_date:
        print(f"  ✓ Empleado ingresó después del 1/ene → proyección proporcional aplicada")
    else:
        print(f"  → Comportamiento año completo (sin ajuste)")

    # Payslips del año
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    slips = Payslip.search([
        ('employee_id', '=', emp.id),
        ('date_to', '>=', year_start),
        ('date_to', '<=', year_end),
        ('state', 'in', ['done', 'paid']),
    ], order='date_to desc')

    print("\n--- 2. RECIBOS DE NÓMINA DEL AÑO ---")
    if not slips:
        print("  No hay recibos confirmados en el año")
    else:
        for s in slips[:5]:
            isr_line = s.line_ids.filtered(lambda l: l.code == 'ISR')
            isr_amt = isr_line.total if isr_line else 0
            print(f"  {s.date_from} - {s.date_to}: ISR={isr_amt:.2f} (estructura: {s.struct_id.code or 'N/A'})")

    # Auditoría ISR
    audits = Audit.search([
        ('employee_id', '=', emp.id),
        ('year', '=', year),
    ], order='period_end desc', limit=5)

    print("\n--- 3. AUDITORÍA ISR (últimos registros) ---")
    if not audits:
        print("  No hay registros de auditoría ISR para este año")
    else:
        for a in audits:
            print(f"  Período {a.period_start} - {a.period_end}:")
            print(f"    projected_annual_income: {a.projected_annual_income:,.2f}")
            print(f"    projected_taxable_base:  {a.projected_taxable_base:,.2f}")
            print(f"    isr_annual_calculated:   {a.isr_annual_calculated:,.2f}")
            print(f"    isr_period_amount:      {a.isr_period_amount:,.2f}")

    # Simular cálculo para el último período o marzo 2026
    print("\n--- 4. SIMULACIÓN DE CÁLCULO ---")
    test_date_from = date(year, 3, 1)
    test_date_to = date(year, 3, 15)
    mock_slip = Payslip.new({
        'employee_id': emp.id,
        'date_from': test_date_from,
        'date_to': test_date_to,
        'company_id': env.company.id,
    })

    if config.multiplicador_tope_exento_decimos:
        salary_ytd = config._get_salary_ytd(emp, year, test_date_to)
        projected_salary = config._project_annual_salary(emp, salary_ytd, test_date_from)
        bonuses_ytd = config._get_bonuses_ytd(emp, year, test_date_to)
        projected_bonuses = config._project_annual_bonuses(emp, bonuses_ytd, test_date_from)

        print(f"  Período simulado: {test_date_from} - {test_date_to}")
        print(f"  salary_ytd:           {salary_ytd:,.2f}")
        print(f"  projected_salary_annual: {projected_salary:,.2f}")
        print(f"  bonuses_ytd:          {bonuses_ytd:,.2f}")
        print(f"  projected_bonuses_annual: {projected_bonuses:,.2f}")

        if hire_date:
            from calendar import monthrange
            hire_month = hire_date.month
            days_in_hire_month = monthrange(year, hire_month)[1]
            days_worked = days_in_hire_month - hire_date.day + 1
            # En Honduras wage se almacena siempre como salario mensual
            monthly_wage = version.wage or 0
            first_month_prop = monthly_wage * (days_worked / float(days_in_hire_month))
            full_months = 12 - hire_month
            expected_proj = first_month_prop + (monthly_wage * full_months)
            print(f"  wage (versión): {version.wage:,.2f} | periodicidad: {version.periodicity or 'N/A'}")
            print(f"  Esperado (mes ingreso proporcional + {full_months} meses): {expected_proj:,.2f}")
            if abs(projected_salary - expected_proj) > 1:
                print(f"  ⚠ Diferencia: {projected_salary - expected_proj:,.2f}")
            else:
                print(f"  ✓ Coincide con proyección")

        calc = config.compute_withholding(mock_slip)
        print(f"  period_amount (retención): {calc.get('period_amount', 0):,.2f}")

    print("\n" + "=" * 70)
