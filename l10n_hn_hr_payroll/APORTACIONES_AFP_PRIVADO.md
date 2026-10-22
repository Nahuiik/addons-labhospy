# Manejo de Aportaciones a AFP Privado por Cuenta Propia

## Descripción

Este documento explica cómo manejar las aportaciones que los empleados hacen directamente a AFP privado por cuenta propia, que **NO se descuentan de la nómina** pero que son **deducibles de la renta anual** para efectos de cálculo de ISR.

## Escenarios Soportados

### 1. Aportación Única Anual
El empleado hace un pago único al año al AFP privado y reporta el monto total a RRHH.

**Ejemplo:**
- Empleado hace un pago único de L 50,000.00 en marzo de 2026
- Este monto es deducible de la renta anual para ISR

### 2. Aportaciones Mensuales Regulares
El empleado se compromete con el AFP a hacer aportaciones mensuales regulares y reporta el monto mensual a RRHH.

**Ejemplo:**
- Empleado se compromete a aportar L 2,000.00 mensuales durante todo el año
- Este monto mensual se acumula y es deducible de la renta anual para ISR

## Cómo Registrar las Aportaciones

### Paso 1: Acceder a Deducciones ISR del Empleado

1. Ir a **Nómina Honduras > Configuración > Deducciones ISR del Empleado**
2. Crear un nuevo registro

### Paso 2: Configurar la Deducción

**Para Aportación Única Anual:**
- **Empleado**: Seleccionar el empleado
- **Año**: 2026 (o el año correspondiente)
- **Tipo de Deducción**: "AFP Privado (Por Cuenta Propia)"
- **Pagado por Cuenta Propia**: ✓ (marcado automáticamente)
- **Monto**: L 50,000.00 (monto total anual)
- **Periodicidad**: "Anual (Aportación Única)"
- **Fecha de Inicio**: Fecha en que se hizo el pago (ej: 2026-03-15)
- **Fecha de Fin**: Dejar vacío o poner la misma fecha de inicio
- **Activo**: ✓

**Para Aportaciones Mensuales Regulares:**
- **Empleado**: Seleccionar el empleado
- **Año**: 2026 (o el año correspondiente)
- **Tipo de Deducción**: "AFP Privado (Por Cuenta Propia)"
- **Pagado por Cuenta Propia**: ✓ (marcado automáticamente)
- **Monto**: L 2,000.00 (monto mensual)
- **Periodicidad**: "Mensual (Aportaciones Regulares)"
- **Fecha de Inicio**: Fecha desde la cual inicia el compromiso (ej: 2026-01-01)
- **Fecha de Fin**: Fecha hasta la cual se comprometió (ej: 2026-12-31) o dejar vacío si es indefinido
- **Activo**: ✓

## Cómo Funciona el Cálculo

### Aportación Única Anual
- El sistema cuenta el monto completo **una sola vez** cuando el período de cálculo incluye la fecha de inicio
- Se suma a las deducciones acumuladas (YTD) del empleado
- Reduce la base gravable anual para el cálculo de ISR

**Ejemplo de Cálculo:**
- Aportación única de L 50,000.00 el 15 de marzo
- En el cálculo de ISR de marzo en adelante, se incluye esta deducción
- Base gravable anual = Ingresos anuales - L 50,000.00 (y otras deducciones)

### Aportaciones Mensuales Regulares
- El sistema cuenta el monto mensual por cada mes desde la fecha de inicio hasta la fecha de fin (o hasta el período actual)
- Se acumula mes a mes en las deducciones YTD
- Reduce la base gravable anual progresivamente

**Ejemplo de Cálculo:**
- Aportación mensual de L 2,000.00 desde enero
- En enero: Deducciones YTD = L 2,000.00
- En febrero: Deducciones YTD = L 4,000.00
- En marzo: Deducciones YTD = L 6,000.00
- ...y así sucesivamente
- Base gravable anual = Ingresos anuales - (L 2,000.00 × meses transcurridos)

## Integración con Cálculo de ISR

Las aportaciones registradas se integran automáticamente en el cálculo de ISR:

1. **Cálculo YTD**: El sistema suma todas las deducciones acumuladas hasta el período actual
2. **Proyección Anual**: Proyecta las deducciones anuales basándose en la periodicidad
3. **Base Gravable**: Reduce la base gravable anual con estas deducciones
4. **Cálculo de ISR**: Calcula el ISR sobre la base gravable reducida
5. **Auditoría**: Registra todas las deducciones en el registro de auditoría ISR

## Campos del Modelo

### Campos Principales
- **Tipo de Deducción**: `'afp'` para AFP Privado por Cuenta Propia
- **Pagado por Cuenta Propia**: Campo booleano que indica que no se descuenta de nómina
- **Monto**: Monto de la deducción (anual o mensual según periodicidad)
- **Periodicidad**: 
  - `'annual'`: Aportación única anual
  - `'monthly'`: Aportaciones mensuales regulares
  - `'per_payslip'`: Por recibo de nómina (no usado para AFP privado)

### Campos de Control
- **Fecha de Inicio**: Fecha desde la cual aplica la deducción
- **Fecha de Fin**: Fecha hasta la cual aplica (vacío = indefinido)
- **Año**: Año fiscal de la deducción
- **Activo**: Si la deducción está activa

## Diferencias con AFP Descontado de Nómina

| Característica | AFP Descontado de Nómina | AFP Privado (Por Cuenta Propia) |
|----------------|---------------------------|----------------------------------|
| **Se descuenta de nómina** | Sí | No |
| **Tipo de deducción** | `'afp_nomina'` | `'afp'` |
| **Pagado por cuenta propia** | No | Sí |
| **Registro** | Se registra en reglas salariales | Se registra en Deducciones ISR del Empleado |
| **Cálculo** | Automático desde nómina | Manual, reportado por empleado |

## Notas Importantes

1. **Verificación**: RRHH debe verificar que el empleado realmente hizo las aportaciones reportadas
2. **Documentación**: Se recomienda mantener comprobantes de las aportaciones
3. **Actualización**: Si cambia el monto mensual, crear un nuevo registro o actualizar el existente
4. **Cancelación**: Si el empleado cancela el compromiso, marcar como inactivo o poner fecha de fin

## Ejemplo Completo

**Escenario**: Empleado Juan Pérez reporta aportación mensual de L 2,500.00 a AFP privado desde enero 2026.

**Registro:**
```
Empleado: Juan Pérez
Año: 2026
Tipo: AFP Privado (Por Cuenta Propia)
Monto: 2,500.00
Periodicidad: Mensual (Aportaciones Regulares)
Fecha Inicio: 2026-01-01
Fecha Fin: (vacío)
Activo: Sí
```

**Cálculo en cada período:**
- Enero: Deducciones YTD = L 2,500.00
- Febrero: Deducciones YTD = L 5,000.00
- Marzo: Deducciones YTD = L 7,500.00
- ...
- Diciembre: Deducciones YTD = L 30,000.00

**Impacto en ISR:**
- Base gravable anual se reduce en L 30,000.00
- ISR anual se calcula sobre la base reducida
- Retención mensual se ajusta según las deducciones acumuladas
