# Cómo se Relacionan los Conceptos Recurrentes con las Reglas Salariales

## Resumen Ejecutivo

Los conceptos recurrentes (`hr.employee.recurring.concept`) se relacionan con las reglas salariales (`hr.salary.rule`) a través de un proceso de transformación en múltiples pasos:

1. **Concepto Recurrente** → Se convierte en **Input de Nómina** (`hr.payslip.input`)
2. **Input de Nómina** → Es accedido por las **Reglas Salariales** mediante código
3. **Regla Salarial** → Calcula el monto y crea una **Línea de Nómina** (`hr.payslip.line`)

## Flujo Completo de Transformación

```
1. Concepto Recurrente (hr.employee.recurring.concept)
   ↓ (sincronización automática cuando se crea/computa nómina)
2. Input de Nómina (hr.payslip.input)
   ↓ (acceso mediante código en reglas salariales)
3. Regla Salarial (hr.salary.rule)
   ↓ (cálculo y aplicación)
4. Línea de Nómina (hr.payslip.line)
```

## Paso 1: Concepto Recurrente → Input de Nómina

### Proceso de Sincronización

Cuando se crea o computa una nómina (`hr.payslip`), el sistema ejecuta automáticamente el método `_sync_recurring_concepts()`:

```python
# En hr.payslip._sync_recurring_concepts()

# 1. Buscar conceptos recurrentes activos del empleado
concepts = env['hr.employee.recurring.concept'].search([
    ('employee_id', '=', employee.id),
    ('active', '=', True),
])

# 2. Filtrar conceptos válidos para el período de la nómina
valid_concepts = []
for concept in concepts:
    # Verificar que el concepto esté activo durante el período
    if concept.date_start and concept.date_start > payslip.date_to:
        continue  # Concepto aún no inicia
    if concept.date_end and concept.date_end < payslip.date_from:
        continue  # Concepto ya terminó
    
    # Para préstamos, verificar que haya cuotas pendientes
    if concept.is_loan:
        if concept.paid_installments >= concept.installments:
            continue  # Préstamo ya pagado
    
    valid_concepts.append(concept)

# 3. Para cada concepto válido, crear un input de nómina
for concept in valid_concepts:
    # Obtener código del concepto maestro
    if concept.master_concept_id and concept.master_concept_id.code:
        input_code = concept.master_concept_id.code  # Ej: 'HOR_EXT'
    else:
        # Fallback: generar código desde el nombre
        input_code = concept.name.upper().replace(' ', '_')[:20]
    
    # Crear o obtener el tipo de input
    input_type = self._get_or_create_input_type(input_code, concept.name)
    
    # Calcular el monto
    amount = self._calculate_concept_amount(concept)
    
    # Crear el input en la nómina
    payslip.input_line_ids = [(0, 0, {
        'name': concept.name,
        'input_type_id': input_type.id,
        'amount': amount,
    })]
```

### Cálculo del Monto

El método `_calculate_concept_amount()` calcula el monto según el tipo:

```python
def _calculate_concept_amount(self, concept):
    """Calculate the amount for a recurring concept"""
    if concept.amount_type == 'fixed':
        return concept.amount  # Monto fijo
    elif concept.amount_type == 'percentage':
        # Porcentaje del salario base
        # Intenta obtener BASIC de las líneas ya calculadas
        if self.line_ids:
            basic_line = self.line_ids.filtered(lambda l: l.code == 'BASIC')
            if basic_line:
                basic_amount = basic_line[0].total
                return (basic_amount * concept.amount) / 100.0
        
        # Si no hay líneas calculadas, usa el salario del contrato
        if self.employee_id.current_version_id:
            wage = self.employee_id.current_version_id.wage or 0.0
            periodicity = self.employee_id.current_version_id.periodicity or 'monthly'
            
            # Ajustar según periodicidad
            if periodicity == 'biweekly':
                period_wage = wage / 2.0
            elif periodicity == 'weekly':
                period_wage = wage / 4.33
            else:  # monthly
                period_wage = wage
            
            return (period_wage * concept.amount) / 100.0
    
    return 0.0
```

## Paso 2: Input de Nómina → Regla Salarial

### Estructura del Input

Un input de nómina tiene:
- **Código** (`code`): Identificador único (ej: `HOR_EXT`, `PRESTAMO`)
- **Nombre** (`name`): Descripción legible
- **Monto** (`amount`): Valor numérico

### Acceso desde Reglas Salariales

Las reglas salariales acceden a los inputs mediante el diccionario `inputs`:

```python
# En una regla salarial (hr.salary.rule)

# Condición: Verificar si existe el input
condition_python: result = 'HOR_EXT' in inputs

# Cálculo: Obtener el monto del input
amount_python_compute:
result = inputs.get('HOR_EXT', 0).amount if 'HOR_EXT' in inputs else 0
```

### Ejemplo de Regla Salarial

```xml
<record id="salary_rule_horas_extra_biweekly" model="hr.salary.rule">
    <field name="code">HOR_EXT</field>
    <field name="name">Horas Extra</field>
    <field name="struct_id" ref="l10n_hn_hr_payroll.structure_biweekly"/>
    <field name="category_id" ref="hr_payroll.ALW"/>
    <field name="sequence">10</field>
    
    <!-- Condición: Solo aplicar si existe el input HOR_EXT -->
    <field name="condition_select">python</field>
    <field name="condition_python">result = 'HOR_EXT' in inputs</field>
    
    <!-- Cálculo: Obtener el monto del input -->
    <field name="amount_select">code</field>
    <field name="amount_python_compute">
result = inputs.get('HOR_EXT', 0).amount if 'HOR_EXT' in inputs else 0
    </field>
    
    <field name="appears_on_payslip" eval="True"/>
</record>
```

## Paso 3: Regla Salarial → Línea de Nómina

Cuando la regla se ejecuta:
1. Verifica la condición: ¿Existe el input `HOR_EXT`?
2. Si existe, calcula el monto: `inputs['HOR_EXT'].amount`
3. Crea una línea de nómina con:
   - `code`: `HOR_EXT`
   - `name`: `Horas Extra`
   - `total`: Monto del input (ej: 500.0)
   - `category_id`: Categoría de la regla (ej: ALW - Allowance)

## Ejemplo Completo: De Concepto Recurrente a Línea de Nómina

### Escenario: Empleado con Horas Extra Recurrentes

**1. Concepto Recurrente Creado:**
```
Empleado: Juan Pérez
Concepto: Horas Extra
Concepto Maestro: Horas Extra (code: HOR_EXT)
Monto: 500.00 (fijo)
Fecha inicio: 2025-01-01
Activo: Sí
```

**2. Nómina Creada:**
```python
payslip = env['hr.payslip'].create({
    'employee_id': juan.id,
    'date_from': '2025-01-01',
    'date_to': '2025-01-15',
    'struct_id': structure_biweekly.id,
})
```

**3. Sincronización Automática:**
```python
# Se ejecuta automáticamente _sync_recurring_concepts()
# Encuentra el concepto "Horas Extra" activo
# Obtiene el código del concepto maestro: 'HOR_EXT'
# Calcula el monto: 500.00
# Crea el input:

payslip.input_line_ids = [
    {
        'name': 'Horas Extra',
        'input_type_id': input_type_hor_ext.id,  # code: 'HOR_EXT'
        'amount': 500.0,
    }
]
```

**4. Cálculo de la Nómina:**
```python
payslip.compute_sheet()
```

**5. Ejecución de Reglas:**
```python
# Regla HOR_EXT se ejecuta:
# 1. Condición: 'HOR_EXT' in inputs → True
# 2. Cálculo: inputs['HOR_EXT'].amount → 500.0
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

## Relación Clave: El Código del Concepto Maestro

### Importancia del Código

El código del concepto maestro (`hr.master.concept.code`) es el **vínculo crítico** entre conceptos recurrentes y reglas salariales:

```
Concepto Maestro
  code: 'HOR_EXT'
    ↓
Concepto Recurrente
  master_concept_id → Concepto Maestro (code: 'HOR_EXT')
    ↓
Input de Nómina
  input_type_id.code → 'HOR_EXT'
    ↓
Regla Salarial
  condition: 'HOR_EXT' in inputs
  amount: inputs['HOR_EXT'].amount
```

### Sin Concepto Maestro

Si un concepto recurrente **no tiene concepto maestro**, el sistema:
1. Genera un código desde el nombre: `concept.name.upper().replace(' ', '_')[:20]`
2. Crea el input con ese código generado
3. **PERO**: Las reglas salariales no lo encontrarán a menos que tengan el mismo código

**Ejemplo:**
```
Concepto Recurrente:
  name: "Bono Especial"
  master_concept_id: False

Código generado: "BONO_ESPECIAL"

Input creado:
  code: "BONO_ESPECIAL"

Regla salarial necesita:
  condition: 'BONO_ESPECIAL' in inputs
```

**Problema:** Si no existe una regla con código `BONO_ESPECIAL`, el concepto no aparecerá en la nómina.

## Tipos de Conceptos y sus Reglas

### 1. Conceptos con Reglas Predefinidas

Estos conceptos tienen reglas salariales ya creadas en las estructuras:

| Concepto | Código | Regla Existe |
|----------|--------|--------------|
| Horas Extra | `HOR_EXT` | Sí |
| Horas de Lactancia | `HL` | Sí |
| Depreciación Vehículo | `DV` | Sí |
| Meriendas | `MERIENDAS` | Sí |
| Vacaciones | `VACACIONES` | Sí |
| Préstamo Personal | `PREST_PERS` | Sí |

**Flujo:**
1. Crear concepto recurrente con concepto maestro que tenga código `HOR_EXT`
2. Al generar nómina, se crea input con código `HOR_EXT`
3. Regla salarial busca `'HOR_EXT' in inputs` → encuentra el input
4. Regla calcula: `inputs['HOR_EXT'].amount`
5. Se crea línea de nómina

### 2. Conceptos Sin Reglas Predefinidas

Si creas un concepto recurrente con un código que no tiene regla:

**Opción A: Crear la Regla Salarial**
```xml
<record id="salary_rule_bono_especial" model="hr.salary.rule">
    <field name="code">BONO_ESPECIAL</field>
    <field name="name">Bono Especial</field>
    <field name="struct_id" ref="l10n_hn_hr_payroll.structure_biweekly"/>
    <field name="condition_python">result = 'BONO_ESPECIAL' in inputs</field>
    <field name="amount_python_compute">
result = inputs.get('BONO_ESPECIAL', 0).amount if 'BONO_ESPECIAL' in inputs else 0
    </field>
</record>
```

**Opción B: Usar Regla Genérica**
Si tienes una regla genérica que suma todos los inputs de una categoría, el concepto aparecerá automáticamente.

## Estructura de Datos

### hr.employee.recurring.concept
```python
{
    'employee_id': 123,
    'name': 'Horas Extra',
    'master_concept_id': 45,  # Concepto Maestro con code='HOR_EXT'
    'amount': 500.0,
    'amount_type': 'fixed',
    'date_start': '2025-01-01',
    'date_end': False,
    'active': True,
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

### hr.salary.rule (acceso a inputs)
```python
# Variables disponibles en reglas:
inputs = {
    'HOR_EXT': <hr.payslip.input object>,
    'HL': <hr.payslip.input object>,
    # ...
}

# Acceso:
inputs['HOR_EXT'].amount  # 500.0
inputs.get('HOR_EXT', 0).amount  # 500.0 (con fallback)
'HOR_EXT' in inputs  # True
```

### hr.payslip.line (resultado final)
```python
{
    'payslip_id': 456,
    'code': 'HOR_EXT',
    'name': 'Horas Extra',
    'total': 500.0,
    'category_id': category_allowance.id,
    'salary_rule_id': rule_hor_ext.id,
}
```

## Flujo Detallado Paso a Paso

### Paso 1: Crear Concepto Recurrente
```
Usuario crea concepto recurrente:
- Empleado: Juan Pérez
- Concepto Maestro: Horas Extra (code: HOR_EXT)
- Monto: 500.00
- Fechas: 2025-01-01 a 2025-12-31
```

### Paso 2: Generar Nómina
```
Usuario crea nómina para Juan Pérez:
- Período: 2025-01-01 a 2025-01-15
- Estructura: Estructura Quincenal Honduras
```

### Paso 3: Sincronización Automática
```
Sistema ejecuta _sync_recurring_concepts():
1. Busca conceptos recurrentes de Juan activos
2. Encuentra "Horas Extra" (válido para el período)
3. Obtiene código del concepto maestro: 'HOR_EXT'
4. Calcula monto: 500.00
5. Crea input: code='HOR_EXT', amount=500.0
```

### Paso 4: Cálculo de Nómina
```
Usuario hace clic en "Calcular Nómina"
Sistema ejecuta compute_sheet():
1. Obtiene todas las reglas de la estructura
2. Ejecuta cada regla en orden (sequence)
3. Regla HOR_EXT:
   - Condición: 'HOR_EXT' in inputs → True
   - Cálculo: inputs['HOR_EXT'].amount → 500.0
   - Crea línea: code='HOR_EXT', total=500.0
```

### Paso 5: Resultado Final
```
Nómina calculada con líneas:
- BASIC: 7,500.00
- HOR_EXT: 500.00  ← Del concepto recurrente
- GROSS: 8,000.00
- IHSS: -150.00
- NET: 7,850.00
```

## Puntos Clave

### 1. El Código es el Vínculo
- El código del concepto maestro debe coincidir con el código que busca la regla salarial
- Sin código coincidente, el concepto no aparecerá en la nómina

### 2. Sincronización Automática
- Los conceptos recurrentes se sincronizan automáticamente cuando se crea/computa la nómina
- No necesitas hacer nada manualmente

### 3. Validación de Períodos
- Solo se incluyen conceptos activos durante el período de la nómina
- Los préstamos se excluyen cuando se completan todas las cuotas

### 4. Cálculo Dinámico
- Los conceptos con `amount_type='percentage'` se calculan dinámicamente según el salario base
- Los conceptos con `amount_type='fixed'` usan el monto fijo

### 5. Múltiples Conceptos con el Mismo Código
- Si hay múltiples conceptos recurrentes con el mismo código, solo se usa uno (el último creado o actualizado)
- Es mejor tener un solo concepto activo por código

## Ejemplos Prácticos

### Ejemplo 1: Concepto con Regla Predefinida

**Concepto Recurrente:**
- Name: Horas Extra
- Master Concept: Horas Extra (code: `HOR_EXT`)
- Amount: 500.00

**Resultado:**
- Input creado: `code='HOR_EXT'`, `amount=500.0`
- Regla encuentra: `'HOR_EXT' in inputs` → True
- Línea creada: `code='HOR_EXT'`, `total=500.0`

### Ejemplo 2: Concepto Sin Concepto Maestro

**Concepto Recurrente:**
- Name: Bono Adicional
- Master Concept: None
- Amount: 200.00

**Resultado:**
- Código generado: `BONO_ADICIONAL`
- Input creado: `code='BONO_ADICIONAL'`, `amount=200.0`
- Regla necesita: `'BONO_ADICIONAL' in inputs`
- **Problema:** Si no existe regla con ese código, no aparecerá en la nómina

### Ejemplo 3: Concepto Porcentual

**Concepto Recurrente:**
- Name: Bono de Productividad
- Master Concept: Bono Prod (code: `BONO_PROD`)
- Amount Type: Percentage
- Amount: 5.0 (5%)

**Resultado:**
- Input creado: `code='BONO_PROD'`
- Monto calculado: `(salario_base * 5) / 100`
- Si salario base = 10,000 → monto = 500.0
- Regla encuentra: `inputs['BONO_PROD'].amount` → 500.0

## Resumen

**Pregunta:** ¿Cómo se relacionan los conceptos recurrentes con las reglas salariales?

**Respuesta:**

1. **Concepto Recurrente** se crea para un empleado con un concepto maestro que tiene un código único
2. Al generar una nómina, el concepto se sincroniza automáticamente como **Input de Nómina** usando el código del concepto maestro
3. Las **Reglas Salariales** buscan inputs por código usando `'CODE' in inputs` y `inputs['CODE'].amount`
4. Si el código coincide, la regla calcula el monto y crea una **Línea de Nómina**

**Vínculo crítico:** El código del concepto maestro debe coincidir con el código que busca la regla salarial.

**Flujo:**
```
Concepto Maestro (code: 'HOR_EXT')
    ↓
Concepto Recurrente (master_concept_id → code: 'HOR_EXT')
    ↓ (sincronización automática)
Input de Nómina (input_type_id.code: 'HOR_EXT')
    ↓ (acceso mediante código)
Regla Salarial (busca 'HOR_EXT' in inputs)
    ↓ (cálculo)
Línea de Nómina (code: 'HOR_EXT', total: 500.0)
```
