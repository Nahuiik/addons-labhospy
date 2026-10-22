#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script SIMPLE para eliminar TODOS los empleados de la base de datos
Ejecutar desde Odoo shell: python3 odoo-bin shell -d GRUPOHMM < delete_all_employees.py

ADVERTENCIA: Este script elimina TODOS los empleados sin confirmación.
Para una versión más segura con opciones, use delete_employees.py
"""

# En el shell de Odoo, cr y env ya están disponibles
# No necesitamos importar nada adicional

print("\n" + "="*80)
print("🗑️  ELIMINANDO TODOS LOS EMPLEADOS")
print("="*80)

# Buscar todos los empleados
employees = env['hr.employee'].search([])
total = len(employees)

if total == 0:
    print("\nℹ️  No hay empleados para eliminar.")
else:
    print(f"\n📋 Encontrados {total} empleados.")
    print("🗑️  Eliminando empleados y datos relacionados...\n")
    
    deleted_count = 0
    error_count = 0
    
    for employee in employees:
        try:
            employee_name = employee.name
            employee_id = employee.id
            
            # PRIMERO: Eliminar líneas salariales con SQL directo (más confiable)
            try:
                env.cr.execute("DELETE FROM hr_employee_salary_line WHERE employee_id = %s", (employee.id,))
                env.cr.commit()
            except Exception as sql_error:
                # Si falla SQL, intentar con ORM
                try:
                    if 'hr.employee.salary.line' in env:
                        salary_lines = env['hr.employee.salary.line'].search([('employee_id', '=', employee.id)])
                        if salary_lines:
                            salary_lines.unlink()
                except:
                    pass
            
            # Eliminar datos relacionados (con manejo de errores si el modelo no existe)
            # IMPORTANTE: Eliminar en orden para evitar problemas de integridad referencial
            
            # 1. Eliminar aumentos salariales (esto eliminará las líneas por cascade si aún existen)
            try:
                if 'hr.salary.increase' in env:
                    increases = env['hr.salary.increase'].search([('employee_id', '=', employee.id)])
                    if increases:
                        increases.unlink()
            except:
                pass
            
            # 3. Eliminar el resto de modelos relacionados
            models_to_clean = [
                ('hr.employee.recurring.concept', 'Conceptos recurrentes'),
                ('hr.employee.salary.input', 'Entradas salariales'),
                ('l10n.hn.isr.employee_deduction', 'Deducciones ISR'),
                ('l10n.hn.isr.audit', 'Auditoría ISR'),
                ('hr.payslip', 'Nóminas'),
                ('hr.version', 'Versiones de contrato'),
                ('salary.advance', 'Anticipos salariales'),
                ('l10n.hn.benefits', 'Beneficios'),
                ('l10n.hn.vecinal.income', 'Ingresos vecinales'),
                ('hr.document', 'Documentos'),
                ('hr.employee.emergency.contact', 'Contactos de emergencia'),
                ('hr.employee.family', 'Familiares'),
                ('hr.license', 'Licencias'),
                ('reference.personal', 'Referencias'),
                ('hr.breastfeeding.hours', 'Horas de lactancia'),
                ('hr.work.certificate', 'Certificados de trabajo'),
            ]
            
            # 4. Eliminar también con SQL directo para tablas que puedan tener problemas
            sql_tables_to_clean = [
                'hr_employee_salary_line',
                'hr_work_certificate',
            ]
            
            for table in sql_tables_to_clean:
                try:
                    env.cr.execute(f"DELETE FROM {table} WHERE employee_id = %s", (employee.id,))
                    env.cr.commit()
                except:
                    pass
            
            for model_name, description in models_to_clean:
                try:
                    if model_name in env:
                        records = env[model_name].search([('employee_id', '=', employee.id)])
                        if records:
                            records.unlink()
                except Exception as e:
                    # Si el modelo no existe o hay error, continuar con el siguiente
                    pass
            
            # Eliminar el empleado
            employee.unlink()
            
            deleted_count += 1
            if deleted_count % 10 == 0:
                print(f"   Procesados {deleted_count}/{total} empleados...")
            
        except Exception as e:
            error_count += 1
            print(f"❌ Error al eliminar {employee.name} (ID: {employee.id}): {str(e)}")
    
    print(f"\n{'='*80}")
    print(f"✅ Eliminación completada:")
    print(f"   • Empleados eliminados: {deleted_count}")
    print(f"   • Errores: {error_count}")
    print(f"{'='*80}\n")
