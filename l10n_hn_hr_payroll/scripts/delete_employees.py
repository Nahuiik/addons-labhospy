#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para eliminar empleados existentes de la base de datos
Ejecutar desde Odoo shell: python3 odoo-bin shell -d GRUPOHMM < delete_employees.py

Opciones de uso:
- Eliminar todos los empleados
- Eliminar empleados de una compañía específica
- Eliminar empleados por filtro personalizado

ADVERTENCIA: Este script elimina permanentemente los empleados y sus datos relacionados.
"""

# En el shell de Odoo, cr y env ya están disponibles automáticamente
# No necesitamos crear un nuevo Environment

# ============================================================================
# CONFIGURACIÓN - Modificar según necesidades
# ============================================================================

# Opción 1: Eliminar TODOS los empleados
DELETE_ALL = False

# Opción 2: Eliminar empleados de una compañía específica
DELETE_BY_COMPANY = False
COMPANY_NAME = "Test Company"  # Nombre de la compañía

# Opción 3: Eliminar empleados por filtro personalizado (usar domain de Odoo)
DELETE_BY_FILTER = False
FILTER_DOMAIN = [('name', 'like', 'Test Employee')]  # Ejemplo: empleados con "Test" en el nombre

# Opción 4: Eliminar empleados por IDs específicos
DELETE_BY_IDS = False
EMPLOYEE_IDS = [1, 2, 3]  # IDs específicos de empleados a eliminar

# Confirmar antes de eliminar (recomendado)
REQUIRE_CONFIRMATION = True

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_employees_to_delete():
    """Obtener lista de empleados a eliminar según la configuración"""
    Employee = env['hr.employee']
    
    if DELETE_BY_IDS:
        employees = Employee.browse(EMPLOYEE_IDS)
        return employees.exists()  # Solo retornar los que existen
    
    elif DELETE_BY_COMPANY:
        company = env['res.company'].search([('name', '=', COMPANY_NAME)], limit=1)
        if not company:
            print(f"❌ No se encontró la compañía: {COMPANY_NAME}")
            return Employee.browse([])
        employees = Employee.search([('company_id', '=', company.id)])
        return employees
    
    elif DELETE_BY_FILTER:
        employees = Employee.search(FILTER_DOMAIN)
        return employees
    
    elif DELETE_ALL:
        employees = Employee.search([])
        return employees
    
    else:
        print("⚠️  Ninguna opción de eliminación está activada.")
        print("   Configure DELETE_ALL, DELETE_BY_COMPANY, DELETE_BY_FILTER o DELETE_BY_IDS")
        return Employee.browse([])


def show_employees_info(employees):
    """Mostrar información de los empleados que se van a eliminar"""
    if not employees:
        print("ℹ️  No hay empleados para eliminar.")
        return
    
    print(f"\n{'='*80}")
    print(f"📋 EMPLEADOS A ELIMINAR: {len(employees)}")
    print(f"{'='*80}")
    
    # Agrupar por compañía
    by_company = {}
    for emp in employees:
        company_name = emp.company_id.name if emp.company_id else "Sin Compañía"
        if company_name not in by_company:
            by_company[company_name] = []
        by_company[company_name].append(emp)
    
    for company_name, emps in by_company.items():
        print(f"\n🏢 Compañía: {company_name} ({len(emps)} empleados)")
        for emp in emps[:10]:  # Mostrar máximo 10 por compañía
            contract_info = f"Contrato: {emp.contract_id.name}" if emp.contract_id else "Sin contrato"
            print(f"   • ID {emp.id}: {emp.name} - {contract_info}")
        if len(emps) > 10:
            print(f"   ... y {len(emps) - 10} empleados más")
    
    print(f"\n{'='*80}")


def delete_related_data(employee):
    """Eliminar datos relacionados antes de eliminar el empleado"""
    deleted_items = []
    
    try:
        # PRIMERO: Eliminar con SQL directo tablas problemáticas
        sql_tables_to_clean = [
            'hr_employee_salary_line',
            'hr_work_certificate',
        ]
        
        for table in sql_tables_to_clean:
            try:
                cr.execute(f"DELETE FROM {table} WHERE employee_id = %s", (employee.id,))
                cr.commit()
            except:
                pass
        
        # Entradas de trabajo RR.HH. (bloquean borrado del empleado en la UI)
        if 'hr.work.entry' in env:
            work_entries = env['hr.work.entry'].search([
                ('employee_id', '=', employee.id)
            ])
            if work_entries:
                count = len(work_entries)
                work_entries.unlink()
                deleted_items.append(f"{count} entradas de trabajo (hr.work.entry)")

        # Eliminar conceptos recurrentes del empleado
        recurring_concepts = env['hr.employee.recurring.concept'].search([
            ('employee_id', '=', employee.id)
        ])
        if recurring_concepts:
            count = len(recurring_concepts)
            recurring_concepts.unlink()
            deleted_items.append(f"{count} conceptos recurrentes")
    
        # Eliminar deducciones ISR del empleado
        isr_deductions = env['l10n.hn.isr.employee_deduction'].search([
            ('employee_id', '=', employee.id)
        ])
        if isr_deductions:
            count = len(isr_deductions)
            isr_deductions.unlink()
            deleted_items.append(f"{count} deducciones ISR")
    
        # Eliminar registros de auditoría ISR
        isr_audits = env['l10n.hn.isr.audit'].search([
            ('employee_id', '=', employee.id)
        ])
        if isr_audits:
            count = len(isr_audits)
            isr_audits.unlink()
            deleted_items.append(f"{count} registros de auditoría ISR")
    
        # Eliminar nóminas (payslips)
        payslips = env['hr.payslip'].search([
            ('employee_id', '=', employee.id)
        ])
        if payslips:
            count = len(payslips)
            payslips.unlink()
            deleted_items.append(f"{count} nóminas")
    
        # Eliminar versiones de contrato (hr.version)
        versions = env['hr.version'].search([
            ('employee_id', '=', employee.id)
        ])
        if versions:
            count = len(versions)
            versions.unlink()
            deleted_items.append(f"{count} versiones de contrato")
    
        # Eliminar aumentos salariales
        salary_increases = env['hr.salary.increase'].search([
            ('employee_id', '=', employee.id)
        ])
        if salary_increases:
            count = len(salary_increases)
            salary_increases.unlink()
            deleted_items.append(f"{count} aumentos salariales")
    
        # Eliminar anticipos salariales
        salary_advances = env['salary.advance'].search([
            ('employee_id', '=', employee.id)
        ])
        if salary_advances:
            count = len(salary_advances)
            salary_advances.unlink()
            deleted_items.append(f"{count} anticipos salariales")
    
        # Eliminar beneficios
        benefits = env['l10n.hn.benefits'].search([
            ('employee_id', '=', employee.id)
        ])
        if benefits:
            count = len(benefits)
            benefits.unlink()
            deleted_items.append(f"{count} beneficios")
    
        # Eliminar ingresos vecinales
        vecinal_incomes = env['l10n.hn.vecinal.income'].search([
            ('employee_id', '=', employee.id)
        ])
        if vecinal_incomes:
            count = len(vecinal_incomes)
            vecinal_incomes.unlink()
            deleted_items.append(f"{count} ingresos vecinales")
    
        # Eliminar documentos del empleado
        documents = env['hr.document'].search([
            ('employee_id', '=', employee.id)
        ])
        if documents:
            count = len(documents)
            documents.unlink()
            deleted_items.append(f"{count} documentos")
    
        # Eliminar contactos de emergencia
        emergency_contacts = env['hr.employee.emergency.contact'].search([
            ('employee_id', '=', employee.id)
        ])
        if emergency_contacts:
            count = len(emergency_contacts)
            emergency_contacts.unlink()
            deleted_items.append(f"{count} contactos de emergencia")
    
        # Eliminar familiares
        family_members = env['hr.employee.family'].search([
            ('employee_id', '=', employee.id)
        ])
        if family_members:
            count = len(family_members)
            family_members.unlink()
            deleted_items.append(f"{count} familiares")
    
        # Eliminar licencias
        licenses = env['hr.license'].search([
            ('employee_id', '=', employee.id)
        ])
        if licenses:
            count = len(licenses)
            licenses.unlink()
            deleted_items.append(f"{count} licencias")
    
        # Eliminar referencias (reference.personal, tab Experiencia y Referencias)
        if 'reference.personal' in env:
            references = env['reference.personal'].search([
                ('employee_id', '=', employee.id)
            ])
            if references:
                count = len(references)
                references.unlink()
                deleted_items.append(f"{count} referencias")
    
        # Eliminar horas de lactancia
        breastfeeding_hours = env['hr.breastfeeding.hours'].search([
            ('employee_id', '=', employee.id)
        ])
        if breastfeeding_hours:
            count = len(breastfeeding_hours)
            breastfeeding_hours.unlink()
            deleted_items.append(f"{count} registros de horas de lactancia")
    
    except Exception as e:
        print(f"⚠️  Error al eliminar datos relacionados para {employee.name}: {str(e)}")

    return deleted_items


def delete_employees(employees):
    """Eliminar empleados y sus datos relacionados"""
    if not employees:
        print("ℹ️  No hay empleados para eliminar.")
        return
    
    deleted_count = 0
    error_count = 0
    
    print(f"\n🗑️  Iniciando eliminación de {len(employees)} empleados...")
    print(f"{'='*80}\n")
    
    for employee in employees:
        try:
            employee_name = employee.name
            employee_id = employee.id
            
            # Eliminar datos relacionados primero
            deleted_items = delete_related_data(employee)
            
            # Eliminar el empleado
            employee.unlink()
            
            deleted_count += 1
            items_str = ", ".join(deleted_items) if deleted_items else "ninguno"
            print(f"✓ Eliminado: {employee_name} (ID: {employee_id}) - Datos relacionados: {items_str}")
            
        except Exception as e:
            error_count += 1
            print(f"❌ Error al eliminar {employee.name} (ID: {employee.id}): {str(e)}")
    
    print(f"\n{'='*80}")
    print(f"✅ Eliminación completada:")
    print(f"   • Empleados eliminados: {deleted_count}")
    print(f"   • Errores: {error_count}")
    print(f"{'='*80}\n")


# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

def main():
    """Función principal"""
    print("\n" + "="*80)
    print("🗑️  SCRIPT DE ELIMINACIÓN DE EMPLEADOS")
    print("="*80)
    print("\n⚠️  ADVERTENCIA: Este script eliminará permanentemente empleados y sus datos relacionados.")
    
    # Obtener empleados a eliminar
    employees = get_employees_to_delete()
    
    if not employees:
        print("\n❌ No se encontraron empleados para eliminar.")
        print("   Verifique la configuración del script.")
        return
    
    # Mostrar información
    show_employees_info(employees)
    
    # Confirmación
    if REQUIRE_CONFIRMATION:
        print("\n⚠️  ¿Está seguro de que desea eliminar estos empleados?")
        print("   Esta acción NO se puede deshacer.")
        response = input("\n   Escriba 'SI' para confirmar: ")
        
        if response.upper() != 'SI':
            print("\n❌ Eliminación cancelada por el usuario.")
            return
    
    # Eliminar empleados
    delete_employees(employees)
    
    print("✅ Script finalizado.\n")


if __name__ == '__main__':
    main()
