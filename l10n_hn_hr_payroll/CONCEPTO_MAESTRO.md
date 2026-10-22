# Cómo Funciona el Concepto Maestro

## ¿Qué es un Concepto Maestro?

Un **Concepto Maestro** (`hr.master.concept`) es una **plantilla o definición estándar** de un concepto de nómina que puede reutilizarse para múltiples empleados. Es como un "catálogo" de conceptos disponibles en el sistema.

## Propósito Principal

El concepto maestro permite:
1. **Estandarizar** los conceptos de nómina en toda la organización
2. **Reutilizar** definiciones sin tener que crear cada concepto desde cero
3. **Asignar masivamente** conceptos a múltiples empleados
4. **Mantener consistencia** en nombres, códigos y configuraciones

## Estructura del Concepto Maestro

### Campos Principales

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| **Code** | Código único del concepto (usado en reglas salariales) | `HOR_EXT`, `PRESTAMO`, `BONO` |
| **Name** | Nombre descriptivo del concepto | "Horas Extra", "Préstamo Personal", "Bono de Productividad" |
| **Concept Type** | Tipo: Ingreso o Deducción | `income` o `deduction` |
| **Amount Type** | Tipo de monto: Fijo o Porcentaje | `fixed` o `percentage` |
| **Default Amount** | Monto por defecto | `500.0` o `10.0` (si es porcentaje) |
| **Is Loan** | Si es un préstamo | `True` o `False` |
| **Default Installments** | Número de cuotas por defecto (si es préstamo) | `12` |

### Campos de Aplicabilidad

| Campo | Descripción | Uso |
|-------|-------------|-----|
| **Applies to All** | Si aplica a todos los empleados | `True` = todos, `False` = específicos |
| **Department IDs** | Departamentos específicos | Solo si `applies_to_all = False` |
| **Job IDs** | Puestos de trabajo específicos | Solo si `applies_to_all = False` |
| **Structure Type IDs** | Tipos de estructura de nómina | Quincenal, Mensual, etc. |

## Flujo de Trabajo

### 1. Crear Concepto Maestro

**Ejemplo: Crear "Horas Extra"**

```
1. Ir a: Honduras Payroll → Configuration → Conceptos → Maestro de Conceptos
2. Crear nuevo concepto maestro:
   - Code: HOR_EXT
   - Name: Horas Extra
   - Concept Type: Income
   - Amount Type: Fixed Amount
   - Default Amount: 0.00 (se ajusta por empleado)
   - Applies to All: False
   - Structure Types: Nómina Quincenal, Nómina Mensual
3. Guardar
```

### 2. Usar Concepto Maestro al Crear Concepto Recurrente

**Opción A: Selección Manual**

```
1. Ir al empleado → Conceptos Recurrentes → Crear
2. Seleccionar "Concepto Maestro": "Horas Extra"
3. Los campos se llenan automáticamente:
   - Name: "Horas Extra" ✓
   - Concept Type: "Income" ✓
   - Amount Type: "Fixed Amount" ✓
4. Ajustar el Amount según el empleado: 500.00
5. Guardar
```

**Opción B: Asignación Masiva**

```
1. Ir al Concepto Maestro "Horas Extra"
2. Clic en botón "Asignar a Empleados Elegibles"
3. El sistema busca empleados que cumplan:
   - Están activos
   - Pertenecen a los departamentos/puestos configurados
   - Tienen el tipo de estructura configurado
4. Crea automáticamente conceptos recurrentes para cada empleado elegible
```

## Relación con Conceptos Recurrentes

### Concepto Maestro vs Concepto Recurrente

| Aspecto | Concepto Maestro | Concepto Recurrente |
|---------|-----------------|---------------------|
| **Alcance** | Organización completa | Empleado específico |
| **Cantidad** | Uno por tipo de concepto | Múltiples por empleado |
| **Propósito** | Plantilla/Definición | Instancia específica |
| **Código** | Único en toda la organización | Hereda del maestro |
| **Monto** | Monto por defecto | Monto específico del empleado |

### Relación en el Modelo

```
hr.master.concept (Concepto Maestro)
    ↓ (referenciado por)
hr.employee.recurring.concept (Concepto Recurrente)
    ↓ (convertido a)
hr.payslip.input (Input de Nómina)
    ↓ (usado por)
hr.salary.rule (Regla Salarial)
```

## Cómo se Usa en las Nóminas

### Paso 1: Concepto Recurrente → Input de Nómina

Cuando se crea o computa una nómina, el sistema sincroniza los conceptos recurrentes:

```python
# En hr.payslip._sync_recurring_concepts()
for concept in valid_concepts:
    # Obtener código del concepto maestro
    if concept.master_concept_id and concept.master_concept_id.code:
        input_code = concept.master_concept_id.code  # 'HOR_EXT'
    else:
        # Fallback si no tiene concepto maestro
        input_code = concept.name.upper().replace(' ', '_')
    
    # Crear input en la nómina
    payslip.input_line_ids = [(0, 0, {
        'name': concept.name,
        'input_type_id': input_type.id,
        'amount': concept.amount,  # Monto específico del empleado
    })]
```

### Paso 2: Input → Regla Salarial

Las reglas salariales acceden a los inputs usando el código:

```python
# Regla salarial para Horas Extra
condition_python: result = 'HOR_EXT' in inputs

amount_python_compute:
result = inputs.get('HOR_EXT', 0).amount if 'HOR_EXT' in inputs else 0
# result = 500.0 (monto del concepto recurrente del empleado)
```

## Ejemplo Completo

### Escenario: Bono de Productividad

**1. Crear Concepto Maestro**

```
Code: BONO_PROD
Name: Bono de Productividad
Concept Type: Income
Amount Type: Percentage
Default Amount: 5.0 (5% del salario base)
Applies to All: False
Departments: Ventas, Marketing
Structure Types: Nómina Mensual
```

**2. Asignar a Empleados**

**Opción A: Manual**
- Empleado: Juan Pérez (Ventas)
- Concepto Maestro: Bono de Productividad
- Amount: 5.0 (porcentaje)
- Date Start: 2025-01-01

**Opción B: Masiva**
- Clic en "Asignar a Empleados Elegibles"
- Sistema crea conceptos recurrentes para:
  - Todos los empleados de Ventas y Marketing
  - Que tengan estructura "Nómina Mensual"
  - Que no tengan ya este concepto activo

**3. En la Nómina**

```
1. Se genera nómina para Juan Pérez (Enero 2025)
2. Sistema sincroniza conceptos recurrentes:
   - Encuentra "Bono de Productividad" activo
   - Código maestro: BONO_PROD
   - Monto: 5.0% (porcentaje)
3. Crea input en nómina:
   - Code: BONO_PROD
   - Amount: Calculado como 5% del salario base
4. Regla salarial aplica:
   - Busca input 'BONO_PROD'
   - Obtiene el monto calculado
   - Crea línea de nómina con el bono
```

## Ventajas del Concepto Maestro

### 1. Consistencia
- Todos los empleados usan el mismo código y nombre
- Facilita reportes y análisis

### 2. Eficiencia
- No hay que crear cada concepto desde cero
- Asignación masiva a múltiples empleados

### 3. Mantenimiento
- Cambios en el concepto maestro pueden propagarse
- Fácil identificar qué conceptos están en uso

### 4. Trazabilidad
- Se puede rastrear qué concepto maestro originó cada concepto recurrente
- Facilita auditorías

## Casos de Uso Comunes

### Caso 1: Préstamos

```
Concepto Maestro:
- Code: PRESTAMO_PERSONAL
- Name: Préstamo Personal
- Concept Type: Deduction
- Amount Type: Fixed
- Is Loan: True
- Default Installments: 12

Concepto Recurrente (por empleado):
- Empleado: María González
- Master Concept: Préstamo Personal
- Amount: 1000.00 (monto de la cuota)
- Total Amount: 12000.00 (monto total del préstamo)
- Installments: 12
- Paid Installments: 0
```

### Caso 2: Beneficios por Departamento

```
Concepto Maestro:
- Code: BONO_VENTAS
- Name: Bono de Ventas
- Concept Type: Income
- Amount Type: Percentage
- Default Amount: 10.0
- Applies to All: False
- Departments: Ventas
- Structure Types: Nómina Mensual

Asignación:
- Clic en "Asignar a Empleados Elegibles"
- Se crean conceptos recurrentes para todos los empleados de Ventas
- Cada empleado puede tener un porcentaje diferente si se ajusta manualmente
```

### Caso 3: Conceptos Universales

```
Concepto Maestro:
- Code: ALMUERZO
- Name: Subsidio de Almuerzo
- Concept Type: Income
- Amount Type: Fixed
- Default Amount: 200.00
- Applies to All: True
- Structure Types: (todos)

Asignación:
- Clic en "Asignar a Empleados Elegibles"
- Se crea para TODOS los empleados activos
- Todos reciben el mismo monto por defecto (200.00)
```

## Mejores Prácticas

### 1. Nomenclatura de Códigos
- Usar códigos descriptivos y únicos
- Ejemplos: `HOR_EXT`, `PRESTAMO`, `BONO_PROD`
- Evitar: `CONCEPTO1`, `TEST`, `ABC`

### 2. Configuración de Aplicabilidad
- Usar `applies_to_all = True` solo para conceptos universales
- Especificar departamentos/puestos cuando sea necesario
- Asociar con tipos de estructura relevantes

### 3. Montos por Defecto
- Establecer montos razonables por defecto
- Permitir ajuste individual cuando sea necesario
- Documentar en la descripción del concepto maestro

### 4. Gestión de Préstamos
- Marcar claramente los conceptos como préstamos
- Configurar número de cuotas por defecto
- Usar el botón "Marcar Cuota Pagada" para seguimiento

## Resumen

El **Concepto Maestro** es una herramienta poderosa que permite:

1. **Definir estándares** de conceptos de nómina
2. **Reutilizar configuraciones** sin duplicar trabajo
3. **Asignar masivamente** conceptos a empleados
4. **Mantener consistencia** en toda la organización
5. **Facilitar el mantenimiento** y actualización

**Flujo típico:**
```
Crear Concepto Maestro → Asignar a Empleados → 
Conceptos Recurrentes → Inputs de Nómina → 
Reglas Salariales → Líneas de Nómina
```

**Beneficio clave:** 
Un concepto maestro puede generar múltiples conceptos recurrentes, cada uno con su configuración específica por empleado, pero manteniendo la consistencia en código y estructura.
