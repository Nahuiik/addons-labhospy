# Scripts para Eliminar Empleados

Este directorio contiene scripts para eliminar empleados de la base de datos de Odoo.

## ⚠️ ADVERTENCIA

**Estos scripts eliminan permanentemente empleados y todos sus datos relacionados. Esta acción NO se puede deshacer.**

Asegúrese de tener un respaldo de la base de datos antes de ejecutar estos scripts.

## Scripts Disponibles

### 1. `delete_employees.py` (Recomendado)

Script completo con opciones de configuración y confirmación.

**Características:**
- Múltiples opciones de filtrado
- Confirmación antes de eliminar
- Información detallada de lo que se va a eliminar
- Manejo de errores

**Opciones de uso:**

#### Opción 1: Eliminar todos los empleados
```python
DELETE_ALL = True
DELETE_BY_COMPANY = False
DELETE_BY_FILTER = False
DELETE_BY_IDS = False
```

#### Opción 2: Eliminar por compañía
```python
DELETE_ALL = False
DELETE_BY_COMPANY = True
COMPANY_NAME = "Mi Compañía"
```

#### Opción 3: Eliminar por filtro personalizado
```python
DELETE_ALL = False
DELETE_BY_FILTER = True
FILTER_DOMAIN = [('name', 'like', 'Test')]  # Empleados con "Test" en el nombre
```

#### Opción 4: Eliminar por IDs específicos
```python
DELETE_ALL = False
DELETE_BY_IDS = True
EMPLOYEE_IDS = [1, 2, 3, 4, 5]
```

**Ejecución:**
```bash
cd /home/odoo/src/nahuiik
python3 /home/odoo/src/odoo/odoo-bin shell -d GRUPOHMM < l10n_hn_hr_payroll/scripts/delete_employees.py
```

### 2. `delete_all_employees.py` (Simple)

Script simple que elimina TODOS los empleados sin confirmación.

**Ejecución:**
```bash
cd /home/odoo/src/nahuiik
python3 /home/odoo/src/odoo/odoo-bin shell -d GRUPOHMM < l10n_hn_hr_payroll/scripts/delete_all_employees.py
```

## Datos que se Eliminan

Los scripts eliminan los siguientes datos relacionados con cada empleado:

- ✅ Conceptos recurrentes (`hr.employee.recurring.concept`)
- ✅ Deducciones ISR (`l10n.hn.isr.employee_deduction`)
- ✅ Registros de auditoría ISR (`l10n.hn.isr.audit`)
- ✅ Nóminas/Payslips (`hr.payslip`)
- ✅ Versiones de contrato (`hr.version`)
- ✅ Aumentos salariales (`hr.salary.increase`)
- ✅ Anticipos salariales (`salary.advance`)
- ✅ Beneficios (`l10n.hn.benefits`)
- ✅ Ingresos vecinales (`l10n.hn.vecinal.income`)
- ✅ Documentos (`hr.document`)
- ✅ Contactos de emergencia (`hr.employee.emergency.contact`)
- ✅ Familiares (`hr.employee.family`)
- ✅ Licencias (`hr.license`)
- ✅ Referencias (`reference.personal`, pestaña Experiencia y Referencias)
- ✅ Horas de lactancia (`hr.breastfeeding.hours`)
- ✅ El empleado mismo (`hr.employee`)

## Ejemplos de Uso

### Ejemplo 1: Eliminar empleados de prueba

Editar `delete_employees.py`:
```python
DELETE_BY_FILTER = True
FILTER_DOMAIN = [('name', 'like', 'Test')]
REQUIRE_CONFIRMATION = True
```

Ejecutar:
```bash
python3 /home/odoo/src/odoo/odoo-bin shell -d GRUPOHMM < l10n_hn_hr_payroll/scripts/delete_employees.py
```

### Ejemplo 2: Eliminar empleados de una compañía específica

Editar `delete_employees.py`:
```python
DELETE_BY_COMPANY = True
COMPANY_NAME = "Compañía de Prueba"
REQUIRE_CONFIRMATION = True
```

Ejecutar:
```bash
python3 /home/odoo/src/odoo/odoo-bin shell -d GRUPOHMM < l10n_hn_hr_payroll/scripts/delete_employees.py
```

### Ejemplo 3: Eliminar empleados específicos por ID

Editar `delete_employees.py`:
```python
DELETE_BY_IDS = True
EMPLOYEE_IDS = [10, 20, 30]
REQUIRE_CONFIRMATION = True
```

Ejecutar:
```bash
python3 /home/odoo/src/odoo/odoo-bin shell -d GRUPOHMM < l10n_hn_hr_payroll/scripts/delete_employees.py
```

## Notas Importantes

1. **Respaldo**: Siempre haga un respaldo de la base de datos antes de ejecutar estos scripts.

2. **Confirmación**: El script `delete_employees.py` requiere escribir 'SI' para confirmar la eliminación.

3. **Errores**: Si algún empleado no se puede eliminar (por ejemplo, por restricciones de integridad referencial), el script continuará con los demás y mostrará un resumen de errores al final.

4. **Rendimiento**: Para grandes cantidades de empleados, el proceso puede tardar varios minutos.

5. **Transacciones**: Los scripts ejecutan las eliminaciones en una transacción. Si hay un error crítico, puede hacer rollback de todos los cambios.

## Solución de Problemas

### Error: "No se puede eliminar porque tiene registros relacionados"

Algunos modelos pueden tener restricciones de integridad referencial. El script intenta eliminar los datos relacionados primero, pero si persiste el error, puede ser necesario:

1. Revisar manualmente qué registros están relacionados
2. Eliminar esos registros manualmente primero
3. Luego ejecutar el script nuevamente

### Error: "Permission denied"

Asegúrese de ejecutar el script con permisos de superusuario o con un usuario que tenga permisos para eliminar empleados.

## Alternativa: Usar la Interfaz de Odoo

Si prefiere usar la interfaz gráfica:

1. Ir a **Recursos Humanos > Empleados**
2. Seleccionar los empleados a eliminar
3. Usar la acción **Eliminar** del menú de acciones

Nota: Esto puede ser más lento para grandes cantidades de empleados.
