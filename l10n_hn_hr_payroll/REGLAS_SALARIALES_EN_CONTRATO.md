# Cómo las Reglas Salariales Terminan en el Contrato del Empleado

## Resumen Ejecutivo

Las reglas salariales (`hr.salary.rule`) no se asignan directamente al contrato del empleado (`hr.version`). En su lugar, existe una cadena de relaciones que conecta las reglas con los contratos a través de las **Estructuras de Nómina** (`hr.payroll.structure`).

## Flujo de Relaciones

```
hr.salary.rule (Regla Salarial)
    ↓ (asignada a)
hr.payroll.structure (Estructura de Nómina)
    ↓ (asociada a)
hr.payroll.structure.type (Tipo de Estructura)
    ↓ (asignado a)
hr.version (Contrato del Empleado)
    ↓ (usado en)
hr.payslip (Nómina)
```

## Componentes del Sistema

### 1. Reglas Salariales (`hr.salary.rule`)

Las reglas salariales son las unidades básicas de cálculo en la nómina. Cada regla define:
- **Código**: Identificador único (ej: `BASIC`, `IHSS`, `ISR`, `RAP`)
- **Nombre**: Descripción legible
- **Categoría**: Tipo de regla (Deducción, Asignación, etc.)
- **Condición**: Cuándo se aplica la regla
- **Cálculo**: Cómo se calcula el monto
- **Estructura**: A qué estructura pertenece (`struct_id`)

**Ejemplo de regla salarial:**
```xml
<record id="salary_rule_ihss_employee_biweekly" model="hr.salary.rule">
    <field name="name">IHSS Empleado</field>
    <field name="code">IHSS_EMP</field>
    <field name="struct_id" ref="l10n_hn_hr_payroll.structure_biweekly"/>
    <field name="category_id" ref="hr_payroll.DED"/>
    <!-- ... condiciones y cálculos ... -->
</record>
```

### 2. Estructura de Nómina (`hr.payroll.structure`)

La estructura de nómina es un **contenedor** que agrupa múltiples reglas salariales relacionadas. Cada estructura tiene:
- **Nombre**: Ej. "Estructura Quincenal Honduras"
- **Código**: Ej. `HN_BIWEEKLY`
- **Tipo**: Referencia a `hr.payroll.structure.type`
- **Reglas**: Todas las reglas salariales que pertenecen a esta estructura

**Ejemplo de estructura:**
```xml
<record id="structure_biweekly" model="hr.payroll.structure">
    <field name="name">Estructura Quincenal Honduras</field>
    <field name="type_id" ref="l10n_hn_hr_payroll.structure_type_biweekly"/>
    <field name="code">HN_BIWEEKLY</field>
</record>
```

**Relación con reglas:**
- Las reglas salariales tienen un campo `struct_id` que las vincula a una estructura
- Una estructura puede tener múltiples reglas
- Una regla pertenece a una sola estructura

### 3. Tipo de Estructura (`hr.payroll.structure.type`)

El tipo de estructura define las características generales de un grupo de estructuras:
- **Nombre**: Ej. "Nómina Quincenal"
- **Frecuencia de pago**: `bi-weekly`, `monthly`, `weekly`
- **Calendario de recursos**: Horario de trabajo por defecto

**Ejemplo de tipo de estructura:**
```xml
<record id="structure_type_biweekly" model="hr.payroll.structure.type">
    <field name="name">Nómina Quincenal</field>
    <field name="default_schedule_pay">bi-weekly</field>
    <field name="default_resource_calendar_id" ref="resource.resource_calendar_std"/>
</record>
```

**Relación con estructuras:**
- Un tipo puede tener múltiples estructuras asociadas
- Una estructura pertenece a un tipo
- El tipo define valores por defecto para los contratos

### 4. Contrato del Empleado (`hr.version`)

El contrato del empleado (`hr.version`) es donde se configura qué estructura de nómina utilizará el empleado:

**Campo clave:**
- `structure_type_id`: Referencia al tipo de estructura (ej: "Nómina Quincenal")

**Cómo se asigna:**
1. Al crear un contrato, se selecciona un `structure_type_id`
2. El sistema automáticamente determina qué estructura usar basándose en:
   - El tipo de estructura seleccionado
   - La empresa del empleado
   - La periodicidad configurada

**Ejemplo en código:**
```python
# En hr.version
structure_type_id = fields.Many2one('hr.payroll.structure.type', 
                                     string='Tipo de Estructura')
```

### 5. Nómina (`hr.payslip`)

Cuando se genera una nómina, el sistema:
1. Toma el contrato del empleado (`hr.version`)
2. Obtiene el `structure_type_id` del contrato
3. Busca la estructura de nómina correspondiente
4. Aplica **todas las reglas salariales** de esa estructura
5. Calcula los montos según las condiciones y fórmulas de cada regla

**Campo clave en payslip:**
- `struct_id`: La estructura de nómina que se está usando
- `version_id`: El contrato del empleado

## Proceso Completo: De Regla a Nómina

### Paso 1: Crear Reglas Salariales
```python
# Se crean reglas salariales y se asignan a una estructura
rule_ihss = env['hr.salary.rule'].create({
    'name': 'IHSS Empleado',
    'code': 'IHSS_EMP',
    'struct_id': structure_biweekly.id,  # ← Asignación a estructura
    'category_id': category_deduction.id,
    # ... condiciones y cálculos ...
})
```

### Paso 2: Crear Estructura de Nómina
```python
# Se crea una estructura y se le asignan reglas
structure = env['hr.payroll.structure'].create({
    'name': 'Estructura Quincenal Honduras',
    'code': 'HN_BIWEEKLY',
    'type_id': structure_type_biweekly.id,  # ← Asignación a tipo
})
# Las reglas ya tienen struct_id apuntando a esta estructura
```

### Paso 3: Crear Tipo de Estructura
```python
# Se crea un tipo de estructura
structure_type = env['hr.payroll.structure.type'].create({
    'name': 'Nómina Quincenal',
    'default_schedule_pay': 'bi-weekly',
})
```

### Paso 4: Asignar Tipo al Contrato
```python
# Al crear un contrato, se selecciona el tipo de estructura
contract = env['hr.version'].create({
    'employee_id': employee.id,
    'structure_type_id': structure_type.id,  # ← Asignación al contrato
    'wage': 15000.0,
    'contract_date_start': '2025-01-01',
})
```

### Paso 5: Generar Nómina
```python
# Al generar una nómina, el sistema:
# 1. Toma el contrato del empleado
# 2. Obtiene structure_type_id del contrato
# 3. Busca la estructura correspondiente
# 4. Aplica todas las reglas de esa estructura

payslip = env['hr.payslip'].create({
    'employee_id': employee.id,
    'version_id': contract.id,  # ← Contrato del empleado
    'date_from': '2025-01-01',
    'date_to': '2025-01-15',
})
# El sistema automáticamente asigna struct_id basándose en el contrato
payslip.compute_sheet()  # Aplica todas las reglas salariales
```

## Visualización en el Sistema

### En el Contrato (`hr.version`)

El usuario ve:
- **Campo**: "Tipo de Estructura" (`structure_type_id`)
- **Valor**: "Nómina Quincenal" (o "Nómina Mensual")
- **Efecto**: Esto determina qué estructura de nómina se usará

### En la Estructura de Nómina

El usuario puede ver:
- **Nombre**: "Estructura Quincenal Honduras"
- **Reglas**: Lista de todas las reglas salariales asociadas
  - BASIC
  - GROSS
  - IHSS_EMP
  - RAP_FOVIIF
  - ISR
  - etc.

### En la Nómina (`hr.payslip`)

El usuario ve:
- **Estructura**: "Estructura Quincenal Honduras"
- **Líneas de nómina**: Cada línea corresponde a una regla salarial aplicada
  - BASIC: 7,500.00
  - GROSS: 7,500.00
  - IHSS_EMP: -150.00
  - RAP_FOVIIF: -50.00
  - ISR: -200.00
  - NET: 7,100.00

## Puntos Clave

1. **Las reglas NO se asignan directamente al contrato**
   - Las reglas pertenecen a estructuras
   - Las estructuras pertenecen a tipos
   - Los contratos usan tipos

2. **Un contrato puede cambiar de estructura**
   - Si cambia el `structure_type_id`, se usará una estructura diferente
   - Esto afecta qué reglas se aplican en las nóminas futuras

3. **Múltiples estructuras pueden compartir el mismo tipo**
   - Ej: "Estructura Quincenal Empresa A" y "Estructura Quincenal Empresa B"
   - Ambas son tipo "Nómina Quincenal" pero tienen reglas diferentes

4. **Las reglas pueden tener condiciones**
   - Una regla puede aplicarse solo si se cumple cierta condición
   - Ej: "Aplicar ISR solo si el ingreso bruto > 10,000"

5. **El orden de las reglas importa**
   - Las reglas tienen un campo `sequence` que determina el orden de cálculo
   - Algunas reglas dependen de los resultados de reglas anteriores

## Ejemplo Práctico

**Escenario**: Empleado con contrato quincenal

1. **Reglas creadas**:
   - `BASIC` → Estructura Quincenal
   - `IHSS_EMP` → Estructura Quincenal
   - `ISR` → Estructura Quincenal

2. **Estructura creada**:
   - "Estructura Quincenal Honduras" contiene las 3 reglas

3. **Tipo creado**:
   - "Nómina Quincenal" → asociado a la estructura

4. **Contrato creado**:
   - Empleado: Juan Pérez
   - Tipo de Estructura: "Nómina Quincenal"
   - Salario: 15,000.00

5. **Nómina generada**:
   - Sistema toma el contrato de Juan
   - Encuentra que usa "Nómina Quincenal"
   - Busca "Estructura Quincenal Honduras"
   - Aplica las 3 reglas:
     - BASIC: 7,500.00 (mitad del salario mensual)
     - IHSS_EMP: -150.00 (calculado según configuración)
     - ISR: -200.00 (calculado según tabla ISR)
   - NET: 7,150.00

## Resumen

**Pregunta**: ¿Cómo las reglas salariales terminan en el contrato del empleado?

**Respuesta**: Las reglas salariales NO terminan directamente en el contrato. En su lugar:
1. Las reglas se agrupan en **Estructuras de Nómina**
2. Las estructuras se clasifican en **Tipos de Estructura**
3. Los contratos seleccionan un **Tipo de Estructura**
4. Cuando se genera una nómina, el sistema busca la estructura correspondiente al tipo del contrato
5. Se aplican todas las reglas de esa estructura

Esta arquitectura permite:
- Reutilizar reglas en múltiples estructuras
- Cambiar estructuras sin modificar contratos individuales
- Mantener consistencia en los cálculos de nómina
- Facilitar la configuración y mantenimiento
