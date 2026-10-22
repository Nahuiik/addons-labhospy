# Análisis de Módulos de Contrato Odoo 18 Enterprise

## 📋 Resumen de Módulos Odoo 18 Enterprise

### 1. **hr_contract_salary** 
**Objetivo:** Configurador de Salarios - Base

**Funcionalidades principales:**
- ✅ **Plantillas de Contrato** (Contract Templates)
  - Crear plantillas reutilizables con parámetros predefinidos
  - Definir tipo de estructura salarial, departamento, puesto, salario mensual
  - Tipo de contrato y responsable de RR.HH

- ✅ **Información Salarial**
  - Tipo de salario (fijo o por hora)
  - Frecuencia de pago (schedule_pay)
  - Salario bruto mensual
  - **Costo anual real** (incluye beneficios)
  - **Costo mensual real**

- ✅ **Beneficios y Deducciones** (Benefits & Deductions)
  - Configurar beneficios **antes de impuestos**
  - Configurar deducciones **después de impuestos**
  - Montos por empleado y por empresa
  - Cálculo automático de costos anuales
  - Templates de beneficios por estructura salarial

- ✅ **Ventaja Salarial (Salary Advantage Template)**
  - Sistema de plantillas para ventajas salariales
  - Códigos únicos para identificar beneficios
  - Límites inferior y superior por beneficio
  - Valores por defecto

---

### 2. **hr_contract_salary_holidays**
**Objetivo:** Integración de Vacaciones con Configurador de Salarios

**Funcionalidades principales:**
- ✅ **Salario con Vacaciones (Salary with Holidays)**
  - Concepto de "sacrificio salarial" por días adicionales
  - Días adicionales de vacaciones como parte del paquete
  - Cálculo automático del salario real considerando vacaciones

- ✅ **Cálculo de Costo Anual**
  - Costo anual real incluye días de vacaciones adicionales
  - Factor de sacrificio basado en días laborales del año
  - Conversión bidireccional: wage ↔ wage_with_holidays

- ✅ **Asignación Automática de Vacaciones**
  - Crear automáticamente asignación de vacaciones desde el contrato
  - Vinculación entre contrato y asignación de vacaciones
  - Configuración de tipo de ausencia por defecto en compañía

- ✅ **Días Laborales por Año**
  - Configuración global de días laborales por año (default: 261)
  - Usado para calcular el ratio de sacrificio salarial

---

### 3. **hr_contract_salary_payroll**
**Objetivo:** Integración con Sistema de Nómina

**Funcionalidades principales:**
- ✅ **Generación de Inputs de Nómina**
  - Beneficios mensuales se convierten automáticamente en inputs de payslip
  - Mapeo de beneficios a códigos de input de nómina
  - Soporte para montos de empleado o empresa

- ✅ **Sincronización Automática**
  - Al generar nómina, se incluyen automáticamente los beneficios
  - Solo beneficios con `include_in_payslip = True` y `periodicity = monthly`
  - Respeta códigos de input definidos en el beneficio

- ✅ **Integración con Estructuras Salariales**
  - Los beneficios se vinculan a tipos de estructura salarial
  - Al seleccionar estructura en contrato, se cargan beneficios relacionados

---

## 📊 Estado Actual del Módulo `l10n_hn_hr_contract`

### ✅ **YA IMPLEMENTADO:**

#### De `hr_contract_salary`:
- ✅ Plantillas de beneficios (`l10n.hn.contract.benefit.template`)
- ✅ Líneas de beneficios en contratos (`l10n.hn.contract.benefit.line`)
- ✅ Cálculo de costos anuales y mensuales (`final_yearly_costs`, `monthly_yearly_costs`)
- ✅ Montos de empleado y empresa
- ✅ Periodicidad (mensual, anual, único)
- ✅ Deducciones (campo `is_deduction`)
- ✅ Factor de conversión salarial según `schedule_pay`

#### De `hr_contract_salary_holidays`:
- ✅ Campo `holidays` (días adicionales)
- ✅ Campo `wage_with_holidays` (salario con vacaciones)
- ✅ Campo `wage_on_signature` (salario al firmar)
- ✅ Cálculo de sacrificio salarial (`_get_yearly_cost_sacrifice_ratio`)
- ✅ Conversión bidireccional wage ↔ wage_with_holidays
- ✅ Método `action_generate_timeoff_allocation()`
- ✅ Método `action_view_leave_allocation()`
- ✅ Configuración en `res.company`:
  - `hr_contract_work_days_per_year`
  - `hr_contract_timeoff_auto_allocation`
  - `hr_contract_timeoff_auto_allocation_type_id`

#### De `hr_contract_salary_payroll`:
- ✅ Generación de inputs en payslip (`hr.payslip.get_inputs()`)
- ✅ Filtrado por `periodicity = monthly` y `include_in_payslip = True`
- ✅ Mapeo a códigos de input
- ✅ Soporte para `amount_source` (empleado o empresa)
- ✅ Carga automática de plantillas al cambiar estructura (`_load_benefit_templates()`)

---

### ❌ **FALTANTE / POR MEJORAR:**

#### 1. **Sistema de Salary Advantage Template** (de `hr_contract_salary`)
- ❌ Modelo `hr.version.advantage.template` completo
- ❌ Métodos `get_attribute()` y `set_attribute_value()` 
- ❌ Integración con sistema de códigos dinámicos
- ℹ️ **Nota:** Tenemos `l10n.hn.contract.benefit.template` que es similar pero más específico

#### 2. **Mejoras en Carga de Plantillas**
- ⚠️ Actualmente se carga al cambiar `struct_id`
- ⚠️ Podría mejorarse para cargar también al cambiar `structure_type_id` (si existe)

#### 3. **Validaciones Adicionales**
- ⚠️ Validar que los códigos de input existan en la estructura salarial
- ⚠️ Validar rangos de beneficios si se implementan límites

#### 4. **UI/UX Mejoras**
- ⚠️ Vista kanban para plantillas de contratos (si aplica)
- ⚠️ Wizard para aplicar plantillas a contratos existentes
- ⚠️ Mejores tooltips y ayuda contextual

#### 5. **Funcionalidades Avanzadas Odoo 18**
- ❌ Historial de cambios en beneficios (si aplica)
- ❌ Comparación de contratos/plantillas
- ❌ Exportación/importación de plantillas

---

## 🎯 Plan de Implementación por Fases

### **FASE 1: Completar Funcionalidades Básicas** ✅ (YA HECHO)
- [x] Beneficios y deducciones
- [x] Costos anuales/mensuales
- [x] Salario con vacaciones
- [x] Integración con nómina

### **FASE 2: Mejoras y Validaciones** (PENDIENTE)
- [ ] Validación de códigos de input en estructura salarial
- [ ] Mejorar carga de plantillas
- [ ] Agregar historial/auditoría

### **FASE 3: Funcionalidades Avanzadas** (OPCIONAL)
- [ ] Sistema de límites (lower/upper bound) para beneficios
- [ ] Wizard de aplicación de plantillas
- [ ] Comparación de contratos

---

## 📝 Notas Técnicas

### Diferencias Odoo 18 vs Odoo 19 CE:
1. **Modelo de Contrato:**
   - Odoo 18: `hr.contract` (Enterprise)
   - Odoo 19 CE: `hr.version` (Community + bi_hr_payroll)

2. **Estructura Salarial:**
   - Odoo 18: `hr.payroll.structure.type` → `hr.payroll.structure`
   - Odoo 19 CE: Similar pero estructura diferente en `bi_hr_payroll`

3. **Beneficios:**
   - Odoo 18: `hr.contract.salary.advantage` + templates
   - Odoo 19 CE: `l10n.hn.contract.benefit.line` + `l10n.hn.contract.benefit.template`

