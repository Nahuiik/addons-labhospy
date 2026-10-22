# Cómo las Reglas Salariales Acceden a Beneficios y Deducciones del Empleado

## Resumen Ejecutivo

Las reglas salariales (`hr.salary.rule`) acceden a los beneficios y deducciones del empleado a través de **múltiples mecanismos**:

1. **Variables disponibles**: `employee`, `payslip`, `contract`, `inputs`
2. **Inputs de nómina**: Conceptos recurrentes convertidos automáticamente en `hr.payslip.input`
3. **Configuraciones del sistema**: Búsqueda de configuraciones como IHSS, RAP, ISR
4. **Datos del contrato**: Acceso directo a campos del empleado y contrato
5. **Cálculos dinámicos**: Las reglas ejecutan código Python para calcular montos

## Variables Disponibles en las Reglas Salariales

Cuando una regla salarial se ejecuta, tiene acceso a las siguientes variables:

### 1. `employee` (hr.employee)
Objeto del empleado con todos sus campos:
- `employee.ihss_excluded` - Si está excluido de IHSS
- `employee.rap_excluded` - Si está excluido de RAP
- `employee.isr_excluded` - Si está excluido de ISR
- `employee.current_version_id` - Contrato actual del empleado
- `employee.wage` - Salario del empleado (legacy)
- `employee.company_id` - Empresa del empleado

### 2. `payslip` (hr.payslip)
Objeto de la nómina actual:
- `payslip.date_from` - Fecha inicio del período
- `payslip.date_to` - Fecha fin del período
- `payslip.company_id` - Empresa
- `payslip.env` - Entorno Odoo para buscar otros modelos
- `payslip.version_id` - Contrato del empleado usado en esta nómina

### 3. `contract` (hr.version)
Contrato del empleado:
- `contract.wage` - Salario del contrato
- `contract.periodicity` - Periodicidad (biweekly, monthly, etc.)
- `contract.structure_type_id` - Tipo de estructura

### 4. `inputs` (dict)
Diccionario de inputs de nómina (`hr.payslip.input`):
- Clave: código del input (ej: `'HOR_EXT'`, `'HL'`, `'DV'`)
- Valor: objeto `hr.payslip.input` con campos:
  - `inputs['CODE'].amount` - Monto del input
  - `inputs['CODE'].name` - Nombre del input

### 5. `categories` (dict)
Diccionario de categorías de reglas ya calculadas:
- `categories['BASIC']` - Resultado de la regla BASIC
- `categories['GROSS']` - Resultado de la regla GROSS
- etc.

## Mecanismos de Acceso a Datos

### Mecanismo 1: Acceso Directo a Campos del Empleado

Las reglas pueden acceder directamente a campos del empleado para condiciones y cálculos:

**Ejemplo: Regla IHSS**
```python
# Condición: Solo aplicar si el empleado NO está excluido
condition_python: result = not employee.ihss_excluded

# Cálculo: Acceder a configuraciones y calcular
amount_python_compute:
result = 0
if not employee.ihss_excluded:
    year = payslip.date_to.year if payslip.date_to else 2026
    # Buscar configuración IHSS
    ihss_settings = payslip.env['l10n.hn.ihss.settings'].search([
        ('year', '=', year),
        ('state', '=', 'validated'),
        ('company_id', '=', payslip.company_id.id)
    ], limit=1)
    if ihss_settings:
        # Calcular según el período
        period_days = (payslip.date_to - payslip.date_from).days + 1
        ceiling_ivm = ihss_settings.get_ceiling_for_period(period_days, 'ivm')
        ivm_amount = -round(ceiling_ivm * (ihss_settings.ivm_employee_rate / 100.0), 2)
        # ... más cálculos ...
        result = ivm_amount + em_amount
```

### Mecanismo 2: Inputs de Nómina (Conceptos Recurrentes)

Los conceptos recurrentes del empleado (`hr.employee.recurring.concept`) se sincronizan automáticamente como inputs cuando se crea o computa una nómina.

**Flujo de Sincronización:**

```
1. Empleado tiene conceptos recurrentes (hr.employee.recurring.concept)
   ↓
2. Al crear/computar nómina, se ejecuta _sync_recurring_concepts()
   ↓
3. Los conceptos válidos se convierten en hr.payslip.input
   ↓
4. Las reglas acceden a estos inputs usando inputs['CODE']
```

**Ejemplo: Concepto Recurrente → Input → Regla**

**Paso 1: Crear Concepto Recurrente**
```python
# En el empleado, crear un concepto recurrente
concept = env['hr.employee.recurring.concept'].create({
    'employee_id': employee.id,
    'name': 'Horas Extra',
    'concept_type': 'income',
    'amount_type': 'fixed',
    'amount': 500.0,
    'master_concept_id': master_concept_horas_extra.id,  # Código: 'HOR_EXT'
    'date_start': '2025-01-01',
    'active': True,
})
```

**Paso 2: Sincronización Automática**
```python
# En hr.payslip._sync_recurring_concepts()
# Cuando se crea/computa la nómina:
for concept in valid_concepts:
    input_code = concept.master_concept_id.code  # 'HOR_EXT'
    input_type = self._get_or_create_input_type(input_code, concept.name)
    amount = self._calculate_concept_amount(concept)
    
    # Crear input en la nómina
    self.write({
        'input_line_ids': [(0, 0, {
            'name': concept.name,
            'input_type_id': input_type.id,
            'amount': amount,  # 500.0
        })]
    })
```

**Paso 3: Regla Accede al Input**
```python
# Regla salarial para Horas Extra
condition_python: result = 'HOR_EXT' in inputs

amount_python_compute:
result = inputs.get('HOR_EXT', 0).amount if 'HOR_EXT' in inputs else 0
# result = 500.0
```

### Mecanismo 3: Búsqueda de Configuraciones

Las reglas pueden buscar configuraciones del sistema para calcular deducciones:

**Ejemplo: Regla RAP**
```python
amount_python_compute:
result = 0
if not employee.rap_excluded:
    year = payslip.date_to.year if payslip.date_to else 2026
    # Buscar configuración RAP
    rap_settings = payslip.env['l10n.hn.rap.settings'].search([
        ('year', '=', year),
        ('state', '=', 'validated'),
        ('company_id', '=', payslip.company_id.id)
    ], limit=1)
    if rap_settings:
        period_days = (payslip.date_to - payslip.date_from).days + 1
        floor = rap_settings.get_foviif_floor_for_period(period_days)
        result = -round(floor * (rap_settings.foviif_employee_rate / 100.0), 2)
```

### Mecanismo 4: Acceso al Contrato Actual

Las reglas pueden acceder al contrato actual del empleado:

**Ejemplo: Regla BASIC**
```python
condition_python:
result = employee.current_version_id and (employee.current_version_id.wage or employee.wage) > 0

amount_python_compute:
result = 0
if employee.current_version_id:
    version = employee.current_version_id
    wage = version.wage or 0.0
    periodicity = version.periodicity or 'monthly'
    if periodicity == 'biweekly':
        result = wage / 2.0  # Dividir salario mensual entre 2
    elif periodicity == 'weekly':
        result = wage / 4.33
    else:
        result = wage
elif employee.wage:
    result = employee.wage
```

### Mecanismo 5: Cálculos Complejos (ISR)

Para cálculos complejos como ISR, las reglas pueden llamar a métodos especializados:

**Ejemplo: Regla ISR**
```python
condition_python: result = not employee.isr_excluded

amount_python_compute:
result = 0
if not employee.isr_excluded:
    # Llamar al método especializado de cálculo ISR
    calculation = payslip.env['l10n.hn.isr.config'].compute_withholding(payslip)
    if calculation:
        result = -calculation.get('period_withholding', 0.0)
```

El método `compute_withholding` internamente:
1. Busca la configuración ISR del año y empresa
2. Calcula el ingreso gravable YTD (year-to-date)
3. Calcula las deducciones YTD
4. Calcula el ISR anual proyectado
5. Calcula el ISR retenido YTD
6. Calcula la retención del período actual

## Flujo Completo: De Concepto Recurrente a Nómina

### Escenario: Empleado con Horas Extra Recurrentes

**1. Configuración del Concepto Recurrente**
```
Empleado: Juan Pérez
Concepto: Horas Extra
Tipo: Ingreso
Monto: 500.00 (fijo)
Código: HOR_EXT
Fecha inicio: 2025-01-01
Activo: Sí
```

**2. Creación de Nómina**
```python
payslip = env['hr.payslip'].create({
    'employee_id': juan.id,
    'date_from': '2025-01-01',
    'date_to': '2025-01-15',
    'struct_id': structure_biweekly.id,
})
```

**3. Sincronización Automática de Conceptos**
```python
# Se ejecuta automáticamente _sync_recurring_concepts()
concepts = env['hr.employee.recurring.concept'].search([
    ('employee_id', '=', juan.id),
    ('active', '=', True),
])

# Para cada concepto válido:
# - Busca el código del concepto maestro
# - Crea/obtiene el tipo de input
# - Calcula el monto
# - Crea el input en la nómina

payslip.input_line_ids = [
    (0, 0, {
        'name': 'Horas Extra',
        'input_type_id': input_type_hor_ext.id,
        'amount': 500.0,
    })
]
```

**4. Cálculo de la Nómina**
```python
payslip.compute_sheet()
```

**5. Ejecución de Reglas**
```python
# Regla HOR_EXT se ejecuta:
# 1. Condición: ¿Existe input 'HOR_EXT'?
condition: 'HOR_EXT' in inputs  # True

# 2. Cálculo: Obtener monto del input
amount: inputs.get('HOR_EXT', 0).amount  # 500.0

# 3. Resultado: Se crea línea de nómina
payslip.line_ids = [
    {
        'code': 'HOR_EXT',
        'name': 'Horas Extra',
        'total': 500.0,
        'category_id': category_allowance.id,
    }
]
```

## Tipos de Beneficios y Deducciones

### 1. Deducciones Legales (Automáticas)

Estas deducciones se calculan automáticamente basándose en configuraciones:

**IHSS:**
- Se calcula según configuración `l10n.hn.ihss.settings`
- Considera el techo IVM y EM
- Verifica si el empleado está excluido (`employee.ihss_excluded`)

**RAP:**
- Se calcula según configuración `l10n.hn.rap.settings`
- Considera el piso FOVIIF
- Verifica si el empleado está excluido (`employee.rap_excluded`)

**ISR:**
- Se calcula usando `l10n.hn.isr.config.compute_withholding()`
- Considera ingresos gravables YTD
- Considera deducciones YTD
- Verifica si el empleado está excluido (`employee.isr_excluded`)

### 2. Conceptos Recurrentes (Manuales)

Estos conceptos se configuran manualmente en el empleado y se sincronizan automáticamente:

**Tipos:**
- **Fijo**: Monto fijo cada período
- **Porcentaje**: Porcentaje del salario base

**Ejemplos:**
- Horas Extra (fijo)
- Depreciación Vehículo (fijo)
- Préstamo (fijo, con número de cuotas)
- Bonificación (porcentaje)

### 3. Conceptos Especiales

**Horas de Lactancia:**
- Se registra en `hr.breastfeeding.hours`
- Se sincroniza como input `HL`
- La regla accede mediante `inputs['HL']`

**Impuesto Vecinal:**
- Se calcula según configuración `l10n.hn.vecinal.settings`
- Considera ingresos del año base
- Se aplica según tramos

## Estructura de Datos

### hr.employee.recurring.concept
```python
{
    'employee_id': 123,
    'name': 'Horas Extra',
    'concept_type': 'income',  # o 'deduction'
    'amount_type': 'fixed',  # o 'percentage'
    'amount': 500.0,
    'master_concept_id': 45,  # Referencia a hr.master.concept
    'date_start': '2025-01-01',
    'date_end': False,
    'active': True,
    'is_loan': False,
    'installments': 0,
}
```

### hr.payslip.input (generado automáticamente)
```python
{
    'payslip_id': 456,
    'input_type_id': 78,  # hr.payslip.input.type con code='HOR_EXT'
    'name': 'Horas Extra',
    'amount': 500.0,
}
```

### hr.salary.rule (acceso a datos)
```python
# Variables disponibles:
employee  # hr.employee
payslip   # hr.payslip
contract  # hr.version (contrato actual)
inputs    # dict de hr.payslip.input por código
categories # dict de resultados de otras reglas

# Ejemplo de uso:
if 'HOR_EXT' in inputs:
    amount = inputs['HOR_EXT'].amount
```

## Ejemplos Prácticos

### Ejemplo 1: Regla de Beneficio (Horas Extra)

**Regla:**
```xml
<record id="salary_rule_horas_extra_biweekly" model="hr.salary.rule">
    <field name="code">HOR_EXT</field>
    <field name="condition_python">result = 'HOR_EXT' in inputs</field>
    <field name="amount_python_compute">
result = inputs.get('HOR_EXT', 0).amount if 'HOR_EXT' in inputs else 0
    </field>
</record>
```

**Flujo:**
1. Empleado tiene concepto recurrente "Horas Extra" con código `HOR_EXT`
2. Al crear nómina, se sincroniza como input con `amount=500.0`
3. Regla verifica: `'HOR_EXT' in inputs` → `True`
4. Regla calcula: `inputs['HOR_EXT'].amount` → `500.0`
5. Se crea línea de nómina con `total=500.0`

### Ejemplo 2: Regla de Deducción Legal (IHSS)

**Regla:**
```xml
<record id="salary_rule_ihss_employee_biweekly" model="hr.salary.rule">
    <field name="code">IHSS_EMP</field>
    <field name="condition_python">result = not employee.ihss_excluded</field>
    <field name="amount_python_compute">
result = 0
if not employee.ihss_excluded:
    year = payslip.date_to.year if payslip.date_to else 2026
    ihss_settings = payslip.env['l10n.hn.ihss.settings'].search([
        ('year', '=', year),
        ('state', '=', 'validated'),
        ('company_id', '=', payslip.company_id.id)
    ], limit=1)
    if ihss_settings:
        period_days = (payslip.date_to - payslip.date_from).days + 1
        ceiling_ivm = ihss_settings.get_ceiling_for_period(period_days, 'ivm')
        ivm_amount = -round(ceiling_ivm * (ihss_settings.ivm_employee_rate / 100.0), 2)
        ceiling_em = ihss_settings.get_ceiling_for_period(period_days, 'em')
        em_amount = -round(ceiling_em * (ihss_settings.em_employee_rate / 100.0), 2)
        result = ivm_amount + em_amount
    </field>
</record>
```

**Flujo:**
1. Regla verifica: `not employee.ihss_excluded` → `True`
2. Busca configuración IHSS del año y empresa
3. Calcula días del período: `(2025-01-15 - 2025-01-01) + 1 = 15`
4. Obtiene techo IVM para 15 días
5. Calcula IVM: `techo * tasa_empleado`
6. Calcula EM: `techo * tasa_empleado`
7. Suma ambas deducciones: `result = -150.0 - 50.0 = -200.0`
8. Se crea línea de nómina con `total=-200.0`

### Ejemplo 3: Regla con Dependencia de Otras Reglas

**Regla GROSS (depende de BASIC y otros ingresos):**
```python
# Regla BASIC se ejecuta primero (sequence=1)
# Regla GROSS se ejecuta después (sequence=2)

amount_python_compute:
result = categories.BASIC + categories.HOR_EXT + categories.HL
# categories.BASIC = 7500.0 (de regla BASIC)
# categories.HOR_EXT = 500.0 (de regla HOR_EXT)
# categories.HL = 200.0 (de regla HL)
# result = 8200.0
```

## Resumen de Mecanismos

| Mecanismo | Uso | Ejemplo |
|-----------|-----|---------|
| **Campos del empleado** | Condiciones y datos básicos | `employee.ihss_excluded`, `employee.current_version_id.wage` |
| **Inputs de nómina** | Conceptos recurrentes | `inputs['HOR_EXT'].amount` |
| **Configuraciones** | Deducciones legales | `payslip.env['l10n.hn.ihss.settings'].search(...)` |
| **Contrato actual** | Salario y periodicidad | `employee.current_version_id.periodicity` |
| **Métodos especializados** | Cálculos complejos | `payslip.env['l10n.hn.isr.config'].compute_withholding(payslip)` |
| **Categorías** | Resultados de otras reglas | `categories.BASIC`, `categories.GROSS` |

## Puntos Clave

1. **Los conceptos recurrentes se sincronizan automáticamente** cuando se crea/computa una nómina
2. **Las reglas acceden a inputs mediante código** (`inputs['CODE']`)
3. **Las deducciones legales se calculan dinámicamente** buscando configuraciones
4. **El orden de ejecución importa** (campo `sequence` en las reglas)
5. **Las reglas pueden depender de otras reglas** usando `categories`
6. **Los cálculos pueden ser simples o complejos** dependiendo de la regla

## Conclusión

Las reglas salariales acceden a beneficios y deducciones del empleado a través de:
- **Inputs de nómina** (para conceptos recurrentes)
- **Configuraciones del sistema** (para deducciones legales)
- **Campos del empleado** (para condiciones y datos básicos)
- **Métodos especializados** (para cálculos complejos)

Esta arquitectura permite:
- Flexibilidad para agregar nuevos conceptos
- Cálculos automáticos de deducciones legales
- Sincronización automática de conceptos recurrentes
- Cálculos complejos mediante métodos especializados
