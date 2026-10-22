# 📋 Funcionalidad de Contratos - Equivalente Odoo 18 Enterprise

## ✅ **FUNCIONALIDAD IMPLEMENTADA**

### 🎯 **1. Widget de Contratos en Vista de Empleado**

**Ubicación:** Header del formulario de empleado (ya existe en Odoo 19 base)

**Cómo funciona:**
- El widget `versions_timeline` está en el **header** del formulario del empleado
- Muestra una línea de tiempo con todas las versiones del contrato
- Permite **crear nuevas versiones** haciendo clic en la línea de tiempo
- Permite **editar contratos existentes** haciendo clic en el contrato correspondiente
- El contrato actual se muestra destacado en la línea de tiempo

**Acceso:**
1. Abrir un empleado
2. En el **header** (arriba del formulario) verás el widget de contratos
3. Hacer clic para crear o editar contratos

---

### 🎯 **2. Formulario de Contrato Completo**

**Cuando abres un contrato** (desde el widget o directamente), verás:

#### **Página: "Salary Information"**

**Campos Base:**
- ✅ Salario (Wage) - mensual
- ✅ Tipo de Contrato
- ✅ Categoría de Pago (Pay Category)
- ✅ Horario de Trabajo

**Información Salarial Adicional (Honduras):**
- ✅ **Salario con Vacaciones** (`wage_with_holidays`)
- ✅ **Salario al Firmar** (`wage_on_signature`)
- ✅ **Días Adicionales de Vacaciones** (`holidays`)
- ✅ **Costo Anual Empresa** (`final_yearly_costs`) - calculado automáticamente
- ✅ **Costo Mensual Empresa** (`monthly_yearly_costs`) - calculado automáticamente
- ✅ Botón "Asignar Vacaciones" - genera asignación automática
- ✅ Botón "Ver Asignación" - muestra la asignación creada

**Beneficios y Deducciones:**
- ✅ Lista completa de beneficios configurados
- ✅ Campos editables:
  - Nombre y código
  - Periodicidad (mensual, anual, único)
  - Monto empleado / Monto empresa
  - Es deducción (sí/no)
  - Enviar a nómina
  - Código de entrada
- ✅ Botón "Aplicar Plantilla de Beneficios" - wizard para aplicar plantillas

---

### 🎯 **3. Vista de Empleado - Página Nómina**

**Ubicación:** Empleado → Pestaña "Nómina" (Payroll)

**Campos visibles:**
- ✅ Salario base (`wage`)
- ✅ Información Salarial Honduras (separador)
  - Salario con Vacaciones
  - Salario al Firmar
  - Días Adicionales de Vacaciones
  - Costo Anual/Mensual Empresa
  - Botones de asignación de vacaciones
- ✅ Beneficios y Deducciones (lista completa)

---

### 🎯 **4. Plantillas de Beneficios**

**Ubicación:** RRHH → Configuración → Beneficios de contrato

**Funcionalidad:**
- ✅ Crear plantillas reutilizables por estructura salarial
- ✅ Definir montos por defecto (empleado y empresa)
- ✅ Configurar periodicidad
- ✅ Asociar códigos de input de nómina
- ✅ Aplicar plantillas a contratos mediante wizard

---

## 📍 **Dónde encontrar cada funcionalidad**

### **1. Crear/Editar Contratos:**
```
Empleados → [Abrir empleado] → Header (arriba) → Widget de Línea de Tiempo
```
- Clic en la línea de tiempo para crear nueva versión
- Clic en un contrato existente para editarlo

### **2. Ver Salario del Empleado:**
```
Empleados → [Abrir empleado] → Pestaña "Nómina"
```
- Sección "Contract Overview" → Campo "Wage"
- Sección "Información Salarial Honduras" → Todos los campos adicionales

### **3. Ver/Editar Contrato Completo:**
```
Desde el widget de contratos → [Abrir contrato] → Pestaña "Salary Information"
```
- Todos los campos del contrato incluyendo beneficios y costos

### **4. Configurar Plantillas de Beneficios:**
```
RRHH → Configuración → Beneficios de contrato
```

---

## 🔧 **Diferencias Odoo 18 vs Odoo 19**

| Característica | Odoo 18 Enterprise | Odoo 19 CE + Módulo |
|----------------|-------------------|---------------------|
| **Modelo de Contrato** | `hr.contract` | `hr.version` |
| **Widget de Contratos** | Widget en header | `versions_timeline` (mismo) |
| **Beneficios** | `hr.contract.salary.advantage` | `l10n.hn.contract.benefit.line` |
| **Salario con Vacaciones** | ✅ | ✅ (implementado) |
| **Costos Anuales** | ✅ | ✅ (implementado) |
| **Asignación Automática** | ✅ | ✅ (implementado) |
| **Inputs de Nómina** | ✅ | ✅ (implementado) |

---

## ✅ **Estado Final**

- ✅ Widget de contratos visible y funcional
- ✅ Formulario de contrato con todos los campos de Odoo 18
- ✅ Salario visible en vista de empleado
- ✅ Beneficios y deducciones funcionando
- ✅ Costos anuales/mensuales calculados
- ✅ Asignación automática de vacaciones
- ✅ Plantillas de beneficios
- ✅ Integración con nómina

**El módulo replica la funcionalidad de Odoo 18 Enterprise en Odoo 19 CE.**

