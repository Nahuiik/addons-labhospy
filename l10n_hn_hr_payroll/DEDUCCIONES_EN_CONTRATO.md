# Deducciones ISR, IHSS y RAP en el Contrato del Empleado

## Resumen

Este documento explica cómo funcionan las deducciones ISR, IHSS y RAP en el sistema de contratos (`hr.version`) y cómo asegurar que aparezcan correctamente.

## Arquitectura Actual

### 1. Modelo `hr.version` (Contrato del Empleado)

El modelo `hr.version` (que representa el contrato del empleado en Odoo 19) ahora incluye:

#### Campos de Estado
- `ihss_excluded`, `rap_excluded`, `isr_excluded`: Indican si el empleado está excluido de cada deducción
- `has_ihss`, `has_rap`, `has_isr`: Indican si el empleado tiene cada deducción activa (computed)

#### Campos de Montos (Computed)
- **IHSS:**
  - `ihss_settings_id`: Configuración IHSS activa
  - `ihss_amount_monthly`: Monto mensual total de IHSS
  - `ihss_amount_biweekly`: Monto quincenal de IHSS
  - `ihss_ivm_amount`: Monto mensual de IVM
  - `ihss_em_amount`: Monto mensual de ENF-MAT

- **RAP:**
  - `rap_settings_id`: Configuración RAP activa
  - `rap_foviif_amount_monthly`: Monto mensual de FOVIIF
  - `rap_foviif_amount_biweekly`: Monto quincenal de FOVIIF

- **ISR:**
  - `isr_config_id`: Configuración ISR activa
  - `isr_employee_deduction_ids`: One2many con las deducciones ISR declaradas del empleado

### 2. Cálculo Automático

Los montos se calculan automáticamente basándose en:
- El salario (`wage`) de la versión del contrato
- Las configuraciones validadas de IHSS, RAP e ISR para el año y empresa correspondiente
- La periodicidad del pago (`periodicity`: monthly/biweekly)

#### Cálculo de IHSS:
```
IVM Mensual = min(salario, techo_IVM) × tasa_empleado_IVM
ENF-MAT Mensual = min(salario, techo_ENF-MAT) × tasa_empleado_ENF-MAT
IHSS Mensual = IVM Mensual + ENF-MAT Mensual
IHSS Quincenal = IHSS Mensual / 2
```

#### Cálculo de RAP (FOVIIF):
```
Si salario > techo_IVM:
    Base FOVIIF = min(salario - techo_IVM, piso_FOVIIF)
    FOVIIF Mensual = Base FOVIIF × tasa_empleado_FOVIIF
    FOVIIF Quincenal = FOVIIF Mensual / 2
Sino:
    FOVIIF = 0
```

### 3. Vista en el Contrato

En el formulario de `hr.version` (contrato del empleado), ahora aparece una pestaña **"Deducciones"** con:

1. **Resumen de Estado:**
   - Campos de exclusión (readonly)
   - Indicadores booleanos de deducciones activas

2. **Pestañas de Detalle:**
   - **IHSS**: Muestra configuración, montos mensuales/quincenales, y desglose IVM/ENF-MAT
   - **RAP**: Muestra configuración y montos de FOVIIF
   - **ISR**: Muestra configuración y lista editable de deducciones ISR declaradas

## Cómo Funciona la Creación Automática

### Al Crear un Empleado Nuevo:

1. **No se crean deducciones automáticamente** al crear el empleado
2. **Cuando se crea la primera versión del contrato** (`hr.version`):
   - Se ejecuta automáticamente `_create_default_deductions()`
   - Se vinculan las deducciones ISR existentes del empleado que coincidan con el período de la versión
   - Los montos de IHSS y RAP se calculan automáticamente basándose en el salario y las configuraciones

### Al Crear una Nueva Versión del Contrato:

1. Se ejecuta `_create_default_deductions()` automáticamente
2. Se vinculan deducciones ISR existentes que se solapen con el período de la versión
3. Los montos de IHSS y RAP se recalculan automáticamente

### Al Crear una Deducción ISR:

1. Al crear un registro en `l10n.hn.isr.employee_deduction`:
   - Se busca automáticamente la versión del contrato que se solape con las fechas de la deducción
   - Se vincula automáticamente a esa versión

## Requisitos para que Aparezcan las Deducciones

### Para IHSS:

1. **Configuración IHSS validada:**
   - Debe existir un registro en `l10n.hn.ihss.settings` con `state='validated'`
   - Debe corresponder al año actual y a la empresa del empleado

2. **Empleado no excluido:**
   - El campo `ihss_excluded` del empleado debe ser `False`

3. **Versión del contrato:**
   - El empleado debe tener una versión activa (`hr.version`)
   - El salario (`wage`) debe estar configurado

### Para RAP:

1. **Configuración RAP validada:**
   - Debe existir un registro en `l10n.hn.rap.settings` con `state='validated'`
   - Debe corresponder al año actual y a la empresa del empleado

2. **Empleado no excluido:**
   - El campo `rap_excluded` del empleado debe ser `False`

3. **Condición de salario:**
   - El salario del empleado debe exceder el techo de IVM (de la configuración IHSS)
   - Solo entonces se aplica FOVIIF

4. **Versión del contrato:**
   - El empleado debe tener una versión activa

### Para ISR:

1. **Configuración ISR validada:**
   - Debe existir un registro en `l10n.hn.isr.config` con `state='validated'`
   - Debe corresponder al año actual y a la empresa del empleado

2. **Empleado no excluido:**
   - El campo `isr_excluded` del empleado debe ser `False`

3. **Deducciones ISR (opcional):**
   - Pueden existir registros en `l10n.hn.isr.employee_deduction` vinculados a la versión
   - Estas se muestran en la pestaña ISR del contrato

## Pasos para Configurar

### 1. Configurar IHSS

```
1. Ir a: Honduras Payroll > Configuration > IHSS Settings
2. Crear o validar una configuración para el año actual y empresa
3. Configurar:
   - Techo IVM mensual
   - Tasa empleado IVM (%)
   - Techo ENF-MAT mensual
   - Tasa empleado ENF-MAT (%)
4. Validar la configuración
```

### 2. Configurar RAP

```
1. Ir a: Honduras Payroll > Configuration > RAP Settings
2. Crear o validar una configuración para el año actual y empresa
3. Configurar:
   - Piso FOVIIF mensual
   - Tasa empleado FOVIIF (%)
4. Validar la configuración
```

### 3. Configurar ISR

```
1. Ir a: Honduras Payroll > Configuration > ISR Configuration
2. Crear o validar una configuración para el año actual y empresa
3. Configurar:
   - Tabla de impuestos (brackets)
   - Reglas deducibles
   - Tipos de entrada deducibles
4. Validar la configuración
```

### 4. Crear Empleado y Contrato

```
1. Crear el empleado en HR > Employees
2. Configurar:
   - Company (empresa)
   - Verificar que no esté excluido de deducciones (ihss_excluded, rap_excluded, isr_excluded)
3. Crear versión del contrato:
   - Ir a la pestaña "Contract" del empleado
   - Crear nueva versión con:
     * Salario (wage)
     * Fecha de inicio
     * Estructura de nómina (structure_type_id)
4. Las deducciones aparecerán automáticamente en la pestaña "Deducciones" de la versión
```

### 5. Agregar Deducciones ISR (Opcional)

```
1. Ir a la versión del contrato del empleado
2. Pestaña "Deducciones" > "ISR"
3. Agregar deducciones ISR declaradas (AFP privado, colegio profesional, etc.)
4. Estas se vincularán automáticamente a la versión
```

## Visualización

### En el Formulario del Contrato (`hr.version`):

- **Pestaña "Deducciones"** muestra:
  - Estado de exclusiones
  - Indicadores de deducciones activas
  - Pestañas separadas para IHSS, RAP e ISR con detalles

### En el Formulario del Empleado:

- Las deducciones también están disponibles en:
  - Pestaña "ISR" del empleado (para deducciones ISR declaradas)
  - Campos computed relacionados con IHSS y RAP

## Notas Importantes

1. **Los montos se calculan automáticamente** basándose en el salario y las configuraciones validadas
2. **Las deducciones ISR declaradas** deben crearse manualmente si el empleado tiene deducciones adicionales (AFP privado, colegio profesional, etc.)
3. **La vinculación es automática** cuando se crean versiones o deducciones
4. **Los montos se actualizan** cuando cambia el salario en una nueva versión del contrato
5. **Las configuraciones deben estar validadas** para que los cálculos funcionen correctamente

## Troubleshooting

### Las deducciones no aparecen:

1. Verificar que existan configuraciones validadas para el año actual
2. Verificar que el empleado no esté excluido (`ihss_excluded`, `rap_excluded`, `isr_excluded`)
3. Verificar que el empleado tenga una versión de contrato activa
4. Verificar que el salario esté configurado en la versión

### Los montos están en cero:

1. Verificar que el salario (`wage`) esté configurado en la versión
2. Para RAP: verificar que el salario exceda el techo de IVM
3. Verificar que las tasas estén configuradas correctamente en las configuraciones

### Las deducciones ISR no se vinculan:

1. Ejecutar manualmente el método `_auto_link_deductions_to_versions()` desde el shell de Odoo
2. Verificar que las fechas de las deducciones se solapen con el período de la versión
