#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Revisar configuración en base de datos GRUPOHMM para deducciones AFP/nómina."""
import os
import sys

# Setup Odoo
sys.path.insert(0, '/home/odoo/src/odoo')
os.environ.setdefault('ODOO_RC', '/home/odoo/.odoorc')

import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-d', 'GRUPOHMM'])

def main():
    with odoo.api.Environment.manage():
        registry = odoo.registry('GRUPOHMM')
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})

            print("=" * 70)
            print("REVISIÓN CONFIGURACIÓN BASE DE DATOS - GRUPOHMM")
            print("=" * 70)

            # 1. Tipos de deducción
            print("\n--- 1. TIPOS DE DEDUCCIÓN (l10n.hn.isr.deduction.type) ---")
            types = env['l10n.hn.isr.deduction.type'].search([])
            for t in types:
                print(f"  {t.code}: {t.name} | is_self_paid={t.is_self_paid} | active={t.active}")

            # 2. Empleado de prueba 1002
            print("\n--- 2. EMPLEADO 'Empleado de prueba 1002' ---")
            emp = env['hr.employee'].search([('name', 'ilike', 'Empleado de prueba 1002')], limit=1)
            if not emp:
                print("  No encontrado")
            else:
                print(f"  ID: {emp.id} | isr_excluded: {emp.isr_excluded} | company: {emp.company_id.name}")

            # 3. Deducciones del empleado
            print("\n--- 3. DEDUCCIONES ISR DEL EMPLEADO (l10n.hn.isr.employee_deduction) ---")
            if emp:
                deductions = env['l10n.hn.isr.employee_deduction'].search([
                    ('employee_id', '=', emp.id)
                ], order='id desc', limit=10)
                for d in deductions:
                    tipo = d.deduction_type_id.code if d.deduction_type_id else 'N/A'
                    apply_q = getattr(d, 'apply_in_quincena', None) or 'both'
                    print(f"  ID {d.id}: {d.name} | tipo={tipo} | amount={d.amount} | "
                          f"periodicity={d.periodicity} | is_self_paid={d.is_self_paid} | "
                          f"year={d.year} | date_start={d.date_start} | apply_in_quincena={apply_q} | "
                          f"active={d.active} | company={d.company_id.name}")

            # 4. Estructuras de nómina
            print("\n--- 4. ESTRUCTURAS DE NÓMINA (hr.payroll.structure) ---")
            structs = env['hr.payroll.structure'].search([])
            for s in structs:
                period = getattr(s, 'periodicity', 'N/A')
                sched = s.type_id.default_schedule_pay if s.type_id else 'N/A'
                print(f"  {s.name} (ID {s.id}) | periodicity={period} | schedule_pay={sched}")

            # 5. Payslips recientes del empleado
            print("\n--- 5. PAYSLIPS RECIENTES DEL EMPLEADO ---")
            if emp:
                slips = env['hr.payslip'].search([
                    ('employee_id', '=', emp.id)
                ], order='id desc', limit=5)
                for slip in slips:
                    print(f"  ID {slip.id}: {slip.date_from} a {slip.date_to} | "
                          f"struct={slip.struct_id.name} | state={slip.state}")

            # 6. Reglas salariales DED_AFP_NOMINA
            print("\n--- 6. REGLAS DED_AFP_NOMINA ---")
            rules = env['hr.salary.rule'].search([('code', '=', 'DED_AFP_NOMINA')])
            for r in rules:
                print(f"  {r.name} | struct={r.struct_id.name} | active={r.active}")

            # 7. Diagnóstico para último payslip
            print("\n--- 7. DIAGNÓSTICO AFP PARA ÚLTIMO PAYSLIP ---")
            if emp:
                slip = env['hr.payslip'].search([
                    ('employee_id', '=', emp.id)
                ], order='id desc', limit=1)
                if slip:
                    info = env['l10n.hn.isr.employee_deduction'].diagnose_afp_for_payslip(slip)
                    for k, v in info.items():
                        print(f"  {k}: {v}")
                else:
                    print("  No hay payslips")

            print("\n" + "=" * 70)

if __name__ == '__main__':
    main()
