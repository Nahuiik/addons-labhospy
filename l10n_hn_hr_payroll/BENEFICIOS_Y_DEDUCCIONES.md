# Beneficios y deducciones – Nómina Honduras (paso a paso)

Este documento describe cómo funcionan los **beneficios** (13° y 14° mes, conceptos recurrentes de ingreso) y las **deducciones** (conceptos recurrentes de deducción, ISR, IHSS, RAP, Impuesto Vecinal, etc.) en el módulo de Nómina Honduras.

---

## 1. Resumen del flujo

- **Beneficios 13° y 14° mes**: se calculan por año y empleado; luego las reglas salariales los leen y los incorporan al recibo cuando corresponde.
- **Conceptos recurrentes (beneficios y deducciones por empleado)**: se definen en el empleado (o desde el maestro de conceptos); al crear o calcular el recibo se sincronizan como **entradas (inputs)** del recibo; las reglas salariales usan esas entradas para calcular montos.
- **Deducciones legales (ISR, IHSS, RAP, Impuesto Vecinal)**: se calculan dentro de las reglas salariales según configuración y datos del empleado/recibo.

---

## 2. Beneficios: 13° y 14° mes

### 2.1 Dónde se gestionan

- **Menú**: Nómina Honduras → **Configuración** → **Benefits**.
  - **13th Month**: 13° mes (aguinaldo).
  - **14th Month**: 14° mes.

### 2.2 Paso a paso: 13° mes

1. **Generar registros del año**  
   - Entrar a **Benefits** → **13th Month**.  
   - Usar el botón/wizard **“Generar 13° mes”** (o **“Calcular 13° Mes”**) para el año deseado.  
   - El sistema crea o actualiza un registro **13th Month** por cada empleado activo para ese año.

2. **Cálculo automático**  
   - Cada registro calcula:
     - **Período**: 1 ene – 31 dic del año.
     - **Días trabajados**: en base a versiones de contrato (`hr.version`), con meses de 30 días.
     - **Monto**: proporcional al salario (considerando cambios de salario en el año):  
       `(salario / 360) × días trabajados`.

3. **Exención ISR (opcional)**  
   - En el registro de 13° mes se puede indicar **ISR Exempt Amount** (hasta 10 salarios mínimos).  
   - Lo que exceda se considera **ISR Taxable Amount** para el cálculo de ISR.

4. **Llevar al recibo de nómina**  
   - En la **nómina normal** (quincenal/mensual), las reglas **13TH_MONTH** y **14TH_MONTH**:
     - Buscan el registro de 13° o 14° mes del empleado y del año del recibo.
     - Si existe y tiene `calculated_amount > 0`, ponen ese monto en el recibo y marcan el beneficio como pagado (`paid = True`, `payslip_id`).
   - Para pagar el 13° o 14° mes se suele usar una **estructura específica** (por ejemplo HN_13TH_MONTH / HN_14TH_MONTH) en un recibo del mes elegido (p. ej. diciembre para 13° y junio para 14°).

### 2.3 Paso a paso: 14° mes

1. **Generar registros**  
   - **Benefits** → **14th Month** → usar el wizard/botón de generación para el año.  
   - Se crean/actualizan registros **14th Month** por empleado.

2. **Cálculo**  
   - **Período de cálculo**: 1 jul (año anterior) – 30 jun (año actual).  
   - Monto proporcional con la misma lógica de 30 días por mes y cambios de salario.

3. **Pago en nómina**  
   - Igual que el 13°: las reglas 14TH_MONTH en la estructura correspondiente leen el registro del empleado/año y llevan el monto al recibo, marcando el beneficio como pagado.

---

## 3. Conceptos recurrentes (beneficios y deducciones por empleado)

Son ingresos o deducciones que se repiten en cada recibo (bonos, préstamos, cuotas, etc.).

### 3.1 Maestro de conceptos (opcional)

- **Menú**: Nómina Honduras → **Gestión** → **Conceptos** → **Maestro de Conceptos**.
- Aquí se definen conceptos tipo plantilla:
  - **Nombre**, **Código** (único).
  - **Tipo**: Ingreso o Deducción.
  - **Tipo de monto**: Fijo o Porcentaje del salario base.
  - **Préstamo**: si aplica, número de cuotas y monto total.
  - **A quién aplica**: todos los empleados, o por departamento/puesto/tipo de estructura.
- **Asignar a empleados**: desde el concepto maestro se puede usar **“Asignar a empleados”** para crear automáticamente **Conceptos Recurrentes** en los empleados que cumplan el criterio.

### 3.2 Conceptos recurrentes por empleado

- **Menú**: Nómina Honduras → **Gestión** → **Conceptos** → **Conceptos Recurrentes**.  
  También desde la ficha del **Empleado** → pestaña **Conceptos Recurrentes**.

**Crear un concepto para un empleado**

1. Crear registro en **Conceptos Recurrentes** (o desde el empleado).
2. Definir:
   - **Empleado**.
   - **Nombre del concepto**.
   - **Tipo**: Ingreso o Deducción.
   - **Tipo de monto**: Fijo o Porcentaje de salario base.
   - **Monto**: valor fijo o porcentaje (0–100).
   - Si es **préstamo**: monto total, número de cuotas; el monto del concepto suele ser la cuota.
   - **Fecha inicio** / **Fecha fin** (opcional): vigencia del concepto.
3. Opcional: vincular un **Concepto maestro** para usar su código en nómina.

### 3.3 Cómo llegan al recibo (sincronización)

1. **Al crear el recibo**  
   - Al crear un recibo de nómina (desde lote o manual), el sistema ejecuta `_sync_recurring_concepts()`:
     - Busca **Conceptos Recurrentes** del empleado activos y vigentes para las fechas del recibo (`date_from`–`date_to`).
     - Para préstamos, solo considera conceptos con cuotas pendientes (`paid_installments < installments`).
     - Por cada concepto válido:
       - Usa el **código** del concepto maestro (o uno derivado del nombre).
       - Obtiene o crea un **Tipo de entrada** (`hr.payslip.input.type`) con ese código.
       - Calcula el monto: fijo o porcentaje del salario base (si el recibo ya tiene líneas, usa BASIC; si no, usa el salario de la versión de contrato).
       - Crea o actualiza una línea en **Entradas del recibo** (`input_line_ids`) con ese tipo y monto.

2. **Al recalcular el recibo**  
   - Al ejecutar **Calcular hoja** (`compute_sheet`), después del cálculo normal se vuelve a llamar `_sync_recurring_concepts()` para actualizar entradas (por si el monto es porcentaje y el salario base ya está calculado).

3. **Reglas salariales que usan las entradas**  
   - Cada regla que debe mostrar un beneficio o deducción recurrente usa en su fórmula algo como:
     - `result = inputs.get('CODIGO', 0).amount` (ingresos).
     - `result = -abs(inputs.get('CODIGO', 0).amount)` (deducciones).
   - El **código** debe coincidir con el del tipo de entrada (que viene del concepto maestro o del nombre).  
   - Si el concepto no tiene maestro con código, el sistema genera un código a partir del nombre (ej. “Bono transporte” → algo como `BONO_TRANSPORTE`); la regla debe usar ese mismo código.

### 3.4 Préstamos (cuotas)

- Si el concepto es **préstamo**:
  - **Monto** del concepto = cuota por período.
  - **Cuotas pagadas**: se puede ir marcando con **“Marcar cuota pagada”** (o el sistema las marca al incluirse en el recibo, según implementación).
  - Cuando `paid_installments >= installments`, el concepto deja de considerarse activo para nuevos recibos.

---

## 4. Deducciones legales y otras deducciones fijas

### 4.1 ISR (Impuesto sobre la Renta)

- **Configuración**: Nómina Honduras → **Configuración** → **ISR Configuration**.
- Se configura por año y empresa: escalas, deducciones permitidas (reglas e inputs), periodicidad (mensual/quincenal), etc.
- **Deducciones declaradas del empleado** (reducen base gravable):  
  Configuración → **Employee ISR Deductions**. Son deducciones que el empleado declara (AFP privado, etc.); no se descuentan de nómina pero sí se consideran para el cálculo del ISR.
- **En el recibo**: la regla **ISR** (código ISR) usa `l10n.hn.isr.config.compute_withholding(payslip)` para calcular la retención del período y escribe el monto (negativo) en la línea del recibo.

### 4.2 IHSS y RAP

- **Configuración**: **IHSS Settings** y **RAP Settings** (Configuración).
- Las reglas salariales correspondientes calculan los montos según salario base y configuraciones; aparecen como líneas de deducción en el recibo.

### 4.3 Impuesto Vecinal

- **Configuración**: Nómina Honduras → **Configuración** → **Impuesto Vecinal** (tramos, ingresos año base, método de deducción).
- **En el recibo**: la regla **HN_VECINAL** busca configuración activa y registro de ingreso anual del empleado; calcula el impuesto anual y lo prorratea al período (quincena/mes) según el método configurado.

---

## 5. Orden recomendado de trabajo (resumen)

| Orden | Acción |
|-------|--------|
| 1 | Configurar **Estructuras salariales** y **Reglas salariales** (incluidas las que usan `inputs.get('CODIGO', ...)`). |
| 2 | Definir **Tipos de entrada** (o dejar que se creen al sincronizar conceptos) y asegurar que los **códigos** coincidan con las reglas. |
| 3 | Opcional: crear **Conceptos maestros** y asignarlos a empleados. |
| 4 | Por empleado: dar de alta **Conceptos Recurrentes** (beneficios y deducciones) con fechas y montos. |
| 5 | Para 13° y 14° mes: **Generar** los beneficios del año desde Benefits → 13th Month / 14th Month. |
| 6 | Crear **recibos** (por lote o uno a uno); al crearlos se sincronizan automáticamente los conceptos recurrentes como entradas. |
| 7 | **Calcular hoja** del recibo; las reglas usan entradas, categorías y configuraciones para calcular cada línea (incluidos 13°/14° mes e ISR/IHSS/RAP/Vecinal). |
| 8 | Validar y pagar; para préstamos, marcar cuotas pagadas si aplica. |

---

## 6. Diagrama de flujo simplificado

```
[Conceptos Maestros] ──(asignar)──► [Conceptos Recurrentes por empleado]
        │                                      │
        │                                      │
[13° / 14° Mes: Generar por año]              │
        │                                      │
        ▼                                      ▼
[Al CREAR recibo] ──────────────────► _sync_recurring_concepts()
        │                              • Lee conceptos recurrentes del empleado
        │                              • Crea/actualiza input_line_ids (entradas)
        ▼
[Al CALCULAR recibo]
        │
        ├─► Reglas BASIC, GROSS, etc.
        ├─► Reglas que usan inputs (ej. inputs.get('PREST_PERS', 0).amount)
        ├─► Reglas 13TH_MONTH / 14TH_MONTH (leen l10n.hn.thirteenth/fourteenth.month)
        ├─► Regla ISR (compute_withholding)
        ├─► Reglas IHSS, RAP, HN_VECINAL
        └─► _sync_recurring_concepts() de nuevo (por si hay montos en %)
        ▼
[Recibo con todas las líneas calculadas]
```

Con esto tienes un paso a paso claro de cómo funcionan beneficios y deducciones en Nómina Honduras.
