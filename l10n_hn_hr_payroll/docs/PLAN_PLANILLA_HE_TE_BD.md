# Plan de Implementación: Planilla de Horas Extra, Turnos Extra y Beneficios/Deducciones

**Fecha:** 2026-02-12  
**Módulo base:** l10n_hn_hr_payroll  
**Objetivo:** Añadir módulo de captura de planilla previa a nómina (HE, TE, BD) con filtro jerárquico, fechas de corte y alineación con Configuración Quincenas.

---

## 1. ANÁLISIS DE LO EXISTENTE EN l10n_hn_hr_payroll

### 1.1 Modelos y conceptos reutilizables

| Componente | Ubicación | Uso previsto |
|------------|-----------|--------------|
| **l10n.hn.payroll.period** | `models/l10n_hn_payroll_period.py` | Períodos quincenales con `period_number` ('1'=1-15, '2'=16-fin), `date_start`, `date_end`, nombre "Nómina para 1er/2do Pago mes-año" |
| **hr.payslip.run** | Extendido en `hr_payslip_run.py` | Vinculado a `payroll_period_id`. Cálculo automático de fechas para quincenal |
| **hr.employee.recurring.concept** | `models/hr_employee_recurring_concept.py` | Conceptos con `apply_biweek`, `amount`, `code`. Se sincronizan a payslip vía `input_line_ids` |
| **hr.version** | Extendido en `hr_version.py` | Contrato con `periodicity`, `wage`, `structure_type_id` |
| **hr.employee** | Extendido en `hr_employee.py` | `parent_id` (jefe), `department_id`, `overtime_hours` (campo simple, no detallado) |
| **Menú Quincenas** | `l10n_hn_payroll_menus.xml` | Honduras Payroll > Configuración > Quincenas |
| **Grupos de seguridad** | `l10n_hn_hr_payroll_security.xml` | group_hr_payroll_admin, group_hr_payroll_user, group_hr_payroll_auditor |

### 1.2 Lo que NO existe actualmente

- Modelo `payroll` (planilla) distinto de `hr.payslip`
- Campos HE detallados (he_25, he_50, he_75, he_100) en contrato o planilla
- Turnos extra (turn_a, turn_b, turn_c)
- Fechas de corte configurables (21 mes ant – 20 mes actual)
- Campo `for_payroll` en conceptos recurrentes (para filtrar en BD)
- Filtro jerárquico "jefes ven solo su personal" en nómina/planilla
- Regla de acceso "Mis Planillas" vs "Todas las Planillas"

---

## 2. FECHAS DE CORTE (requerimiento del usuario)

### 2.1 Regla de negocio

> Las HE generadas del **21 del mes anterior** hasta el **20 del mes en curso** se pagan en la **segunda quincena**.

### 2.2 Opciones de diseño

| Opción | Descripción | Pros / Contras |
|--------|-------------|----------------|
| **A** | Configurable por empresa en un modelo `l10n.hn.payroll.cutoff.config` | Flexible, se adapta a cambios regulatorios | Más complejo, requiere UI de configuración |
| **B** | Parámetros fijos: día inicio = 21, día fin = 20 (para segunda quincena) | Simple, cumple el caso descrito | Menos flexible |
| **C** | Campos en `l10n.hn.payroll.period` (ej. `cutoff_start_day`, `cutoff_end_day`) | Centralizado con quincenas | Mezcla conceptos (período de pago vs período de corte) |

**Decisión:** Opción A con valores por defecto (21, 20) para segunda quincena.

### 2.3 Modelo propuesto: `l10n.hn.payroll.cutoff.config`

```
Campos:
- company_id
- year (opcional, para cambios por año)
- period_number: '1' | '2'
- cutoff_start_day: día inicio del rango (ej. 21)
- cutoff_end_day: día fin del rango (ej. 20)
- cutoff_from_previous_month: Boolean (si cutoff_start_day aplica al mes anterior)
```

**Cálculo de fechas de corte para Segunda Quincena (ejemplo 21-20):**
- Si estamos en planilla "2da Quincena Feb-2026" (16 feb – 28 feb):
  - Período de HE a incluir: 21 ene 2026 – 20 feb 2026

---

## 3. INTEGRACIÓN CON CONFIGURACIÓN QUINCENAS

### 3.1 Nombres de planilla

Usar el mismo patrón que `l10n.hn.payroll.period`:

- `get_name()` → "Planilla para 1ra Quincena MMM-YYYY" / "Planilla para 2da Quincena MMM-YYYY"
- O alinear con el nombre ya usado: "Nómina para 1er Pago enero-2026" / "Nómina para 2do Pago enero-2026"

**Propuesta:** Mantener consistencia con `l10n.hn.payroll.period.name` y reutilizar su lógica en el modelo `payroll`.

### 3.2 Vincular planilla a quincena

- `payroll.payroll_period_id` → `l10n.hn.payroll.period`
- Al crear planilla: usuario selecciona quincena (mes, año, 1ra/2da) o se infiere de fecha
- Las fechas de corte se calculan a partir de `payroll_period_id` + configuración de corte

---

## 4. FILTRO JERÁRQUICO (JEFES VEN SOLO SU PERSONAL)

### 4.1 Jerarquía en Odoo

- `hr.employee.parent_id` → jefe directo
- `hr.employee.child_ids` → subordinados directos (campo inverso de `parent_id`)

### 4.2 Estrategias posibles

| Estrategia | Implementación | Alcance |
|------------|----------------|---------|
| **Solo directos** | `employee.parent_id.user_id = uid` (si el usuario está vinculado al jefe) | Solo subordinados directos |
| **Todos los niveles** | Recursión: `child_ids` + `child_ids.child_ids` + … | Subordinados directos e indirectos |
| **Por departamento** | `department_id.manager_id.user_id = uid` o `member_of_department` | Quienes reportan al jefe de departamento |

### 4.3 Recomendación

- **user_only_own:** Ve solo sus propias planillas (creadas por él)
- **user_manager_payroll:** Ve planillas de empleados donde `employee.parent_id.user_id = uid` (subordinados directos)
- **Administrador:** Ve todas las planillas (sin restricción por jerarquía)

Implementar con `ir.rule` (reglas de dominio) en el modelo `payroll`:

1. Sin grupo especial → solo las propias
2. Con `user_manager_payroll` → propias + de subordinados directos
3. Con `group_hr_payroll_admin` → sin restricción (o regla explícita que permita todo)

### 4.4 Determinación de "subordinados"

```python
def _get_subordinate_employee_ids(self, user):
    """Empleados que reportan a este usuario (como parent)"""
    if not user:
        return self.env['hr.employee']
    manager = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
    if not manager:
        return self.env['hr.employee']
    return manager.child_ids  # Solo directos, o recursivo si se requiere
```

---

## 5. ESTRUCTURA DEL MÓDULO NUEVO vs EXTENDER l10n_hn_hr_payroll

### 5.1 Opción A: Extender l10n_hn_hr_payroll

- Añadir modelos `payroll`, `payroll.line`, `payroll.line.te`, `payroll.line.bd`, `extra.hours.register`
- Añadir herencias en `hr.contract` (o `hr.version`)
- Ventaja: un solo módulo
- Desventaja: módulo más pesado, mezcla responsabilidades

### 5.2 Opción B: Módulo separado (ej. gn_l10n_payroll)

- Depende de `l10n_hn_hr_payroll`
- Contiene planilla, HE, TE, BD
- Ventaja: separación de responsabilidades, se puede desactivar si no se usa
- Desventaja: más dependencias y coordinación entre módulos

**Decisión:** Implementar todo dentro de `l10n_hn_hr_payroll`.

---

## 6. PLAN DE IMPLEMENTACIÓN POR FASES

### Fase 0: Preparación (sin código funcional)

- [ ] Crear `l10n.hn.payroll.cutoff.config` (o similar) en l10n_hn_hr_payroll para fechas de corte
- [ ] Añadir `for_payroll` a `hr.employee.recurring.concept` si se usa como catálogo de conceptos BD
- [ ] Decidir nombres exactos: "Planilla" vs "Nómina" en la UI

### Fase 1: Configuración de fechas de corte

1. Modelo `l10n.hn.payroll.cutoff.config`
2. Vista y menú bajo Honduras Payroll > Configuración
3. Método helper `get_cutoff_dates(period)` → (date_from, date_to) para el rango de HE
4. Integración con `l10n.hn.payroll.period`

### Fase 2: Modelo base de Planilla

1. Modelo `payroll` (o `l10n.hn.payroll.sheet`)
   - `name`, `payroll_period_id`, `date_start`, `date_end`, `cutoff_date_from`, `cutoff_date_to`
   - `user_id`, `department_id` (opcional filtro)
   - `state`: draft, done
   - `line_ids`, `line_te_ids`, `line_bd_ids`
2. Método `get_name()` usando `l10n.hn.payroll.period`
3. Creación de planilla: selección de `payroll_period_id` o fecha

### Fase 3: Horas Extra (HE)

1. Modelo `payroll.line` (o `l10n.hn.payroll.line.he`)
   - `contract_id`, `parent_id` (payroll), `he_25`, `he_50`, `he_75`, `he_100`
   - `amount_25`, `amount_50`, `amount_75`, `amount_100`, `amount_total`
2. Modelo `extra.hours.register`
   - `contract_id`, `payroll_id`, `he_*`, `amount_*`
3. Herencia en `hr.version`: `extra_hour_ids` (One2many)
4. Fórmulas de cálculo (wage/240, factores 1.25, 1.5, 1.75, 2)
5. Botón "Obtener Empleados HE" → contratos activos en el período de corte

### Fase 4: Turnos Extra (TE)

1. Modelo `payroll.line.te`
   - `contract_id`, `parent_id`, `turn_a`, `turn_b`, `turn_c`
   - `amount_other_income` (computado)
2. Fórmula: `(wage/30) * (turn_a + turn_b + turn_c)` (o con factores si se definen)
3. Botón "Obtener Empleados TE"

### Fase 5: Beneficios y Deducciones (BD)

1. Campo `for_payroll` en `hr.employee.recurring.concept`
2. Modelo `payroll.line.bd`
   - `contract_id`, `parent_id`, `concept_id`, `amount`, `include_in`
3. Al confirmar: crear/actualizar líneas en conceptos recurrentes del empleado (o en estructura equivalente a `allowences_ids` si existe)
4. Botón "Obtener Empleados BD"

### Fase 6: Acciones y flujo

1. Botón **Confirmar:** aplica fórmulas, crea `extra.hours.register`, escribe en contrato, invoca `update_payroll()` (o equivalente para reflejar en nómina)
2. Botón **Establecer a Borrador:** elimina `extra.hours.register` de la planilla
3. Botón **Limpiar Líneas:** borra todas las líneas y registros asociados

### Fase 7: Seguridad y visibilidad jerárquica

1. Grupos:
   - `user_manager_payroll`: puede confirmar planillas
   - `user_only_own`: ve solo sus planillas
   - `group_payroll` (o admin): puede reestablecer a borrador
2. `ir.rule` para dominio de planillas según jerarquía (`parent_id` → `child_ids`)
3. Menús: "Mis Planillas", "Todas las Planillas" (según grupo)

### Fase 8: Integración con hr.payslip / hr.payslip.run

1. Al generar nómina desde `hr.payslip.run`:
   - Si existe planilla confirmada para el mismo `payroll_period_id`:
   - Tomar `overtime_pay` de `extra.hours.register` (o equivalente)
   - Tomar conceptos BD ya creados
2. Reglas salariales: inputs o categorías que lean de versión/contrato (`overtime_pay`, `amount_other_income`)

---

## 7. MAPA DE ARCHIVOS (PROPUESTO)

### En l10n_hn_hr_payroll (extensiones)

```
models/
  l10n_hn_payroll_cutoff.py   # Nuevo: configuración fechas de corte
  hr_employee_recurring_concept.py  # Añadir for_payroll

views/
  l10n_hn_payroll_cutoff_views.xml  # Nuevo
  l10n_hn_payroll_menus.xml        # Menú Configuración > Fechas de corte

data/
  l10n_hn_payroll_cutoff_data.xml   # Valores por defecto 21-20 para 2da quincena
```

### En gn_l10n_payroll (módulo nuevo)

```
models/
  payroll.py           # payroll, payroll.line, payroll.line.te, payroll.line.bd
  extra_hours_reg.py   # extra.hours.register, herencia hr.version

views/
  payroll_views.xml
  hr_version_views.xml # heredar para mostrar extra_hour_ids

security/
  ir.model.access.csv
  payroll_groups.xml   # user_manager_payroll, user_only_own, group_payroll
  ir_rule_payroll.xml  # Reglas de dominio para "solo mi equipo"

wizard/
  (si se necesita wizard para crear planilla desde quincena)
```

---

## 8. DECISIONES PENDIENTES

| # | Tema | Opciones | Recomendación |
|---|------|----------|---------------|
| 1 | ¿Fechas de corte en l10n_hn o en gn_l10n? | l10n_hn (base) vs gn (específico) | l10n_hn: es configuración de Honduras |
| 2 | Profundidad jerárquica | Solo directos vs recursivo | Empezar con directos; recursivo como mejora |
| 3 | Filtro por departamento en "Obtener Empleados" | Sí/No, configurable | Sí, con checkbox "Solo mi departamento" en planilla |
| 4 | `allowences_ids` vs `hr.employee.recurring.concept` | Cuál usar para BD | Recurring concepts ya existen y se sincronizan a payslip; usarlos |
| 5 | Campos overtime en hr.version | ¿Existen en Odoo 19? | Revisar hr_contract/hr_version; si no, añadir en herencia |

---

## 9. CRONOGRAMA SUGERIDO (estimado)

| Fase | Duración estimada |
|------|-------------------|
| Fase 0 + 1: Corte y for_payroll | 1-2 días |
| Fase 2: Modelo planilla base | 1 día |
| Fase 3: HE + extra.hours.register | 2 días |
| Fase 4: TE | 0.5 día |
| Fase 5: BD | 1 día |
| Fase 6: Acciones y flujo | 1 día |
| Fase 7: Seguridad y jerarquía | 1 día |
| Fase 8: Integración payslip | 1-2 días |
| Pruebas y ajustes | 1-2 días |

**Total aproximado:** 10-12 días de desarrollo.

---

## 10. SIGUIENTE PASO

1. **Nombre UI:** Planilla
2. **Ubicación:** Dentro de l10n_hn_hr_payroll
3. **Estado:** Implementación ejecutada
