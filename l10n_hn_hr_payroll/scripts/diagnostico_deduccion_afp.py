#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico: por qué la deducción AFP aparece en 0 en el payslip.
Ejecutar en shell de Odoo:
  odoo-bin shell -d GRUPOHMM
  >>> exec(open('addons/l10n_hn_hr_payroll/scripts/diagnostico_deduccion_afp.py').read())
O desde el directorio del módulo:
  >>> exec(open('scripts/diagnostico_deduccion_afp.py').read())
"""
# Ajustar: ID del payslip a diagnosticar, o nombre del empleado
PAYSLIP_ID = None  # ej: 12345
EMPLOYEE_NAME = "Empleado de prueba 1002"

def run():
    Deduction = env['l10n.hn.isr.employee_deduction']
    Payslip = env['hr.payslip']
    Employee = env['hr.employee']

    # Buscar payslip
    if PAYSLIP_ID:
        payslip = Payslip.browse(PAYSLIP_ID)
    else:
        emp = Employee.search([('name', 'ilike', EMPLOYEE_NAME)], limit=1)
        if not emp:
            print(f"❌ No se encontró empleado con nombre similar a '{EMPLOYEE_NAME}'")
            return
        payslip = Payslip.search([
            ('employee_id', '=', emp.id),
            ('state', 'in', ['draft', 'done', 'paid'])
        ], order='id desc', limit=1)

    if not payslip or not payslip.exists():
        print("❌ No se encontró payslip. Ajuste PAYSLIP_ID o EMPLOYEE_NAME.")
        return

    print("=" * 60)
    print("DIAGNÓSTICO DEDUCCIÓN AFP - PAYSLIP")
    print("=" * 60)
    print(f"Payslip ID: {payslip.id}")
    print(f"Empleado: {payslip.employee_id.name}")
    print(f"Estructura: {payslip.struct_id.name} (ID: {payslip.struct_id.id})")
    print(f"Período: {payslip.date_from} a {payslip.date_to}")
    print(f"Empresa: {payslip.company_id.name}")
    print(f"employee.isr_excluded: {payslip.employee_id.isr_excluded}")
    print()

    # Detectar si es quincenal
    struct = payslip.struct_id
    is_biweekly = False
    if struct:
        p = getattr(struct, 'periodicity', None)
        if p in ('biweekly', 'bi-weekly'):
            is_biweekly = True
        elif struct.type_id:
            sched = struct.type_id.default_schedule_pay or 'monthly'
            is_biweekly = sched in ('bi-weekly', 'biweekly')
    print(f"¿Nómina quincenal? {is_biweekly}")
    if is_biweekly:
        is_first = payslip.date_to and payslip.date_to.day <= 15
        print(f"¿1ra quincena (date_to.day<=15)? {is_first}")
    print()

    # Buscar deducciones AFP tipo afp_nomina
    deductions = Deduction.search([
        ('employee_id', '=', payslip.employee_id.id),
        ('year', '=', payslip.date_from.year),
        ('active', '=', True),
        ('is_self_paid', '=', False),
        ('company_id', '=', payslip.company_id.id),
        ('deduction_type_id.code', '=', 'afp_nomina'),
    ])
    print(f"Deducciones encontradas (afp_nomina, is_self_paid=False): {len(deductions)}")
    if not deductions:
        print("❌ No hay deducciones que coincidan con el filtro.")
        print("   Verifique: employee_id, year, active, is_self_paid=False, company_id, tipo=afp_nomina")
        return

    for d in deductions:
        print("-" * 40)
        print(f"Deducción ID {d.id}: {d.name}")
        print(f"  Monto: {d.amount}, Periodicidad: {d.periodicity}")
        print(f"  date_start: {d.date_start}, date_end: {d.date_end}")
        print(f"  apply_in_quincena: {d.apply_in_quincena}")
        base = d.get_amount_for_period(payslip.date_from, payslip.date_to)
        print(f"  get_amount_for_period({payslip.date_from}, {payslip.date_to}) = {base}")
        if base == 0:
            if d.date_start > payslip.date_to:
                print("  → date_start > period_end: deducción inicia después del período")
            elif d.date_end and d.date_end < payslip.date_from:
                print("  → date_end < period_start: deducción ya terminó")
            else:
                print("  → Revisar solapamiento de fechas")
        else:
            amt = d.get_amount_for_payslip(payslip)
            print(f"  get_amount_for_payslip() = {amt}")
            if amt == 0 and base > 0:
                if is_biweekly and d.apply_in_quincena == 'second' and payslip.date_to.day <= 15:
                    print("  → apply_in_quincena='second' pero payslip es 1ra quincena → 0")
                elif is_biweekly and d.apply_in_quincena == 'first' and payslip.date_to.day > 15:
                    print("  → apply_in_quincena='first' pero payslip es 2da quincena → 0")

    total = Deduction.get_amount_by_type_for_payslip(payslip, 'afp_nomina')
    print()
    print(f"Total get_amount_by_type_for_payslip(afp_nomina): {total}")
    print("=" * 60)

run()
