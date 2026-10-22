# -*- coding: utf-8 -*-
"""
Script de diagnóstico: verificar configuración de incapacidad (ausencia) para un empleado.

Ejecutar en shell de Odoo:
  odoo-bin shell -d TU_BASE_DE_DATOS
  >>> employee_name = "JAN CARLOS GONZALES MALDONADO"
  >>> exec(open('addons/l10n_hn_hr_payroll/scripts/diagnostico_incapacidad_empleado.py').read())

O con employee_id:
  >>> employee_id = 123
  >>> exec(open('addons/l10n_hn_hr_payroll/scripts/diagnostico_incapacidad_empleado.py').read())
"""
from datetime import date, timedelta

env = globals().get('env')
if not env:
    print("Ejecutar dentro del shell de Odoo")
    raise SystemExit(1)

employee_name = globals().get('employee_name', 'JAN CARLOS GONZALES MALDONADO')
employee_id = globals().get('employee_id')

Employee = env['hr.employee']
if employee_id:
    employees = Employee.browse(employee_id)
else:
    employees = Employee.search([('name', 'ilike', employee_name)])

if not employees:
    print(f"No se encontró empleado con nombre similar a '{employee_name}'")
    raise SystemExit(0)

for emp in employees:
    print("\n" + "=" * 70)
    print(f"EMPLEADO: {emp.name} (ID: {emp.id})")
    print("=" * 70)

    version = emp.current_version_id
    struct = version.struct_id if version else None

    # 1. Contrato / Versión
    print("\n--- 1. CONTRATO (hr.version) ---")
    if not version:
        print("  ❌ NO tiene contrato activo (current_version_id)")
        print("  >>> Crear o activar un contrato para el empleado")
    else:
        print(f"  ✓ Contrato: {version.display_name}")
        print(f"    Fechas: {version.date_start} a {version.date_end or 'indefinido'}")
        print(f"    Salario: {version.wage}")
        print(f"    Estructura: {struct.name if struct else 'N/A'} ({struct.code if struct else 'N/A'})")

        # Calendario de trabajo (CRÍTICO para work entries)
        cal = version.resource_calendar_id
        if not cal:
            print("  ❌ NO tiene Calendario de trabajo (resource_calendar_id)")
            print("  >>> Asignar un calendario al contrato (ej: Jornada 44h Honduras)")
        else:
            print(f"  ✓ Calendario: {cal.name}")

    # 2. Estructura - use_worked_day_lines
    print("\n--- 2. ESTRUCTURA SALARIAL ---")
    if not struct:
        print("  ❌ No hay estructura asignada")
    else:
        use_wd = struct.use_worked_day_lines
        unpaid = struct.unpaid_work_entry_type_ids
        print(f"  use_worked_day_lines: {use_wd} {'✓' if use_wd else '❌ DEBE SER True'}")
        print(f"  unpaid_work_entry_type_ids: {unpaid.mapped('name')}")
        if not use_wd:
            print("  >>> Actualizar módulo l10n_hn_hr_payroll para activar use_worked_day_lines")

    # 3. Ausencias (hr.leave)
    print("\n--- 3. AUSENCIAS (hr.leave) ---")
    if 'hr.leave' not in env:
        print("  ❌ Módulo hr_holidays no instalado")
    else:
        leaves = env['hr.leave'].search([
            ('employee_id', '=', emp.id),
            ('state', 'in', ['validate', 'validate1'])
        ], order='date_from desc', limit=10)
        if not leaves:
            print("  (No hay ausencias aprobadas)")
            print("  >>> Crear ausencia en Tiempo libre y aprobarla")
        else:
            for lv in leaves:
                lt = lv.holiday_status_id
                wet = lt.work_entry_type_id if lt else None
                ok = "✓" if wet else "❌"
                print(f"  • {lt.name if lt else 'N/A'}: {lv.date_from.date()} a {lv.date_to.date()}")
                print(f"    Tipo entrada trabajo: {wet.name if wet else 'NO CONFIGURADO'} {ok}")
                if not wet:
                    print("    >>> En Tiempo libre > Config > Tipos de licencia, asignar 'Tipo de entrada de trabajo'")

    # 4. Tipos de licencia sin work_entry_type_id
    print("\n--- 4. TIPOS DE LICENCIA (configuración global) ---")
    if 'hr.leave.type' in env:
        leave_types = env['hr.leave.type'].search([])
        sin_mapeo = leave_types.filtered(lambda t: not t.work_entry_type_id)
        if sin_mapeo:
            print("  Tipos SIN Tipo de entrada de trabajo (no afectarán nómina):")
            for lt in sin_mapeo:
                print(f"    - {lt.name}")
        else:
            print("  ✓ Todos los tipos tienen work_entry_type_id")

    # 5. Último payslip y worked_days
    print("\n--- 5. ÚLTIMO PAYSLIP ---")
    slip = env['hr.payslip'].search([
        ('employee_id', '=', emp.id)
    ], order='date_to desc', limit=1)
    if slip:
        print(f"  {slip.name}: {slip.date_from} a {slip.date_to}")
        print(f"  Estado: {slip.state}")
        wd_lines = slip.worked_days_line_ids
        if wd_lines:
            print("  Días trabajados:")
            for wd in wd_lines:
                print(f"    - {wd.work_entry_type_id.name}: {wd.number_of_days} días, {wd.number_of_hours} hrs, monto={wd.amount}")
        else:
            print("  (No hay líneas de días trabajados)")
            if struct and struct.use_worked_day_lines:
                print("  >>> Regenerar entradas de trabajo y recalcular la hoja")
    else:
        print("  (No hay payslips)")

    # 6. Work entries recientes
    print("\n--- 6. ENTRADAS DE TRABAJO (últimos 30 días) ---")
    if version and 'hr.work.entry' in env:
        hoy = date.today()
        desde = hoy - timedelta(days=30)
        we = env['hr.work.entry'].search([
            ('employee_id', '=', emp.id),
            ('date', '>=', desde),
        ], order='date desc', limit=20)
        if not we:
            print("  (No hay entradas de trabajo)")
            print("  >>> Nómina > Entradas de trabajo > Regenerar entradas")
        else:
            by_type = {}
            for e in we:
                t = e.work_entry_type_id.name
                by_type[t] = by_type.get(t, 0) + 1
            for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
                print(f"    {t}: {c} días")

    print("\n" + "=" * 70)
    print("RESUMEN: Para que la incapacidad afecte el payslip:")
    print("  1. Contrato con Calendario de trabajo asignado")
    print("  2. Estructura con use_worked_day_lines = True")
    print("  3. Tipo de licencia con Tipo de entrada de trabajo (ej: Sick / Unpaid)")
    print("  4. Ausencia aprobada en Tiempo libre")
    print("  5. Regenerar entradas de trabajo si hace falta")
    print("  6. Calcular hoja en el payslip")
    print("=" * 70)
