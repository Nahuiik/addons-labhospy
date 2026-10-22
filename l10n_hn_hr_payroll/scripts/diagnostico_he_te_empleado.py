#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico HE/TE para un empleado específico.
Ejecutar desde Odoo shell (desde raíz del proyecto Odoo):
  odoo-bin shell -d TU_BD -c odoo.conf
  >>> exec(open('addons/l10n_hn_hr_payroll/scripts/diagnostico_he_te_empleado.py').read())
  >>> diagnostico_he_te('ADALID HERNAN MARTINEZ RIVERA')

O con nombre parcial:
  >>> diagnostico_he_te('ADALID')

Nota: env está disponible en el shell de Odoo.
"""


def diagnostico_he_te(nombre_empleado, env=None):
    """Diagnóstico de por qué no aparecen HE y TE en la nómina de un empleado."""
    if env is None:
        try:
            env = globals()['env']
        except KeyError:
            print("Error: debe ejecutarse desde Odoo shell (env disponible) o pasar env como argumento.")
            return
    Employee = env['hr.employee']
    Version = env['hr.version']
    Register = env['l10n.hn.extra.hours.register']
    Sheet = env['l10n.hn.payroll.sheet']
    Payslip = env['hr.payslip']

    # Buscar empleado
    emp = Employee.search([('name', 'ilike', nombre_empleado)], limit=1)
    if not emp:
        print(f"❌ No se encontró empleado con nombre similar a: {nombre_empleado}")
        return

    emp = emp[0]
    print(f"\n{'='*60}")
    print(f"DIAGNÓSTICO HE/TE - {emp.name} (ID: {emp.id})")
    print(f"{'='*60}\n")

    # 1. Versión actual
    current = emp.current_version_id
    print("1. CONTRATO ACTUAL (current_version_id)")
    if not current:
        print("   ❌ El empleado NO tiene current_version_id (sin contrato activo)")
    else:
        print(f"   ✓ Versión ID: {current.id}")
        print(f"   ✓ Período: {current.contract_date_start} a {current.contract_date_end or 'abierto'}")
        print(f"   ✓ amount_other_income (TE): {current.amount_other_income}")

    # 2. Todas las versiones del empleado
    versions = Version.search([('employee_id', '=', emp.id)], order='contract_date_start desc')
    print(f"\n2. VERSIONES DE CONTRATO ({len(versions)} total)")
    for v in versions[:5]:
        te_val = f", TE={v.amount_other_income}" if hasattr(v, 'amount_other_income') else ""
        print(f"   - ID {v.id}: {v.contract_date_start} a {v.contract_date_end or 'abierto'}{te_val}")

    # 3. Registros HE (l10n.hn.extra.hours.register)
    he_regs = Register.search([('version_id.employee_id', '=', emp.id)])
    print(f"\n3. REGISTROS HORAS EXTRA (l10n.hn.extra.hours.register): {len(he_regs)}")
    for r in he_regs[:10]:
        sheet = r.payroll_sheet_id
        total = (r.amount_25 or 0) + (r.amount_50 or 0) + (r.amount_75 or 0) + (r.amount_100 or 0)
        sheet_period = f"{sheet.date_start} - {sheet.date_end}" if sheet else "N/A"
        print(f"   - version_id={r.version_id.id}, planilla={sheet.name if sheet else 'N/A'} ({sheet_period}), total={total}")

    # 4. Planillas con este empleado (HE o TE)
    sheets_he = Sheet.search([
        ('line_ids.employee_id', '=', emp.id),
        ('state', '=', 'done'),
    ])
    sheets_te = Sheet.search([
        ('line_te_ids.employee_id', '=', emp.id),
        ('state', '=', 'done'),
    ])
    print(f"\n4. PLANILLAS CONFIRMADAS con este empleado")
    print(f"   - En HE: {len(sheets_he)} planillas")
    for s in sheets_he[:5]:
        line = s.line_ids.filtered(lambda l: l.employee_id == emp)
        print(f"     • {s.name} ({s.date_start} - {s.date_end}), amount_total={line.amount_total if line else 0}")
    print(f"   - En TE: {len(sheets_te)} planillas")
    for s in sheets_te[:5]:
        line = s.line_te_ids.filtered(lambda l: l.employee_id == emp)
        print(f"     • {s.name} ({s.date_start} - {s.date_end}), amount_other_income={line.amount_other_income if line else 0}")

    # 5. Payslips del empleado
    slips = Payslip.search([('employee_id', '=', emp.id)], order='date_to desc', limit=5)
    print(f"\n5. ÚLTIMOS PAYSLIPS")
    for slip in slips:
        he_input = slip.input_line_ids.filtered(lambda l: l.input_type_id.code == 'HOR_EXT')
        oi_input = slip.input_line_ids.filtered(lambda l: l.input_type_id.code == 'OI')
        he_amt = he_input[0].amount if he_input else 0
        oi_amt = oi_input[0].amount if oi_input else 0
        # Versión que usaría _get_version_for_period
        version_period = Payslip._get_version_for_period(emp, slip.date_from, slip.date_to)
        print(f"   - {slip.date_from} a {slip.date_to} | estado={slip.state}")
        print(f"     HOR_EXT={he_amt}, OI={oi_amt}")
        print(f"     version_id para período: {version_period.id if version_period else 'NINGUNA'}")

    # 6. Diagnóstico
    print(f"\n6. POSIBLES CAUSAS si HE/TE no aparecen:")
    if not current:
        print("   • Empleado sin contrato (current_version_id vacío)")
    if not he_regs and (sheets_he or sheets_te):
        print("   • Hay planillas confirmadas pero no hay registros HE: ¿Se confirmó la planilla después de crear el payslip?")
    if he_regs:
        version_ids_he = set(he_regs.mapped('version_id').ids)
        print(f"   • HE están en version_ids: {version_ids_he}")
        print("   • El payslip busca en la versión activa durante su período. Si esa versión es distinta, no encuentra HE.")
    print(f"\n{'='*60}\n")
