# Manual de Uso - Módulo de Anticipos de Clientes

## Índice
1. [Introducción](#introducción)
2. [Configuración Inicial](#configuración-inicial)
3. [Registrar un Anticipo](#registrar-un-anticipo)
4. [Aplicar Anticipo desde la Factura](#aplicar-anticipo-desde-la-factura)
5. [Aplicar Anticipo desde el Pago](#aplicar-anticipo-desde-el-pago)
6. [Consultar Anticipos](#consultar-anticipos)
7. [Ver Aplicaciones de Anticipos](#ver-aplicaciones-de-anticipos)
8. [Cancelar Factura con Anticipo Aplicado](#cancelar-factura-con-anticipo-aplicado)
9. [Casos de Uso Comunes](#casos-de-uso-comunes)
10. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## Introducción

El módulo de **Anticipos de Clientes** permite gestionar pagos anticipados de clientes que se registran en una cuenta de pasivo corriente conciliable y se aplican posteriormente a facturas del mismo cliente mediante una reclasificación contable automática.

### Flujo Contable

1. **Anticipo Recibido**: Se registra en pasivo corriente (Anticipos de clientes)
2. **Factura Emitida**: Se registra normalmente en cuentas por cobrar
3. **Aplicación de Anticipo**: Se reclasifica automáticamente de pasivo a CxC y se concilia con la factura

---

## Configuración Inicial

### Paso 1: Acceder a Configuración

1. Ir a **Contabilidad → Configuración → Ajustes**
2. Buscar la sección **"Anticipos de Clientes"**

### Paso 2: Configurar Parámetros

#### Cuenta de Anticipo por Defecto
- Seleccionar la cuenta contable de pasivo corriente conciliable que se usará por defecto para anticipos
- Esta cuenta debe ser:
  - Tipo: Pasivo Corriente
  - Conciliable: Sí
  - Activa: Sí

#### Diario de Reclasificación
- Seleccionar el diario contable que se usará para crear los asientos de reclasificación
- Recomendado: Diario General o Diario de Varios

#### Origen de Fecha del Asiento
- **Fecha de Factura**: El asiento de reclasificación usará la fecha de la factura
- **Fecha Actual**: El asiento de reclasificación usará la fecha del día en que se aplica

#### Permitir Fraccionar Anticipo
- Si está marcado, permite aplicar un anticipo a múltiples facturas
- Si no está marcado, el anticipo debe aplicarse completo a una sola factura

### Paso 3: Guardar Configuración

Hacer clic en **"Guardar"** para aplicar los cambios.

---

## Registrar un Anticipo

### Método 1: Desde el Menú de Anticipos

1. Ir a **Contabilidad → Clientes → Anticipos**
2. Hacer clic en **"Crear"**
3. Completar los campos del pago:
   - **Partner**: Seleccionar el cliente
   - **Tipo de Pago**: Debe ser "Recibir Dinero" (inbound)
   - **Es Anticipo de Cliente**: ✅ Marcar este checkbox
   - **Cuenta de Anticipo**: Se carga automáticamente desde configuración (se puede cambiar)
   - **Diario**: Seleccionar el diario de pago
   - **Monto**: Ingresar el monto del anticipo
   - **Fecha**: Fecha del anticipo
   - **Referencia**: Opcional, número de referencia del pago
4. Hacer clic en **"Validar"**

### Método 2: Desde Pagos Normales

1. Ir a **Contabilidad → Clientes → Pagos**
2. Crear un nuevo pago de tipo "Recibir Dinero"
3. Seleccionar el cliente
4. Marcar el checkbox **"Es Anticipo de Cliente"**
5. Completar los demás campos y validar

### Verificación del Anticipo

Después de validar, el pago mostrará:
- **Saldo Disponible del Anticipo**: Monto que aún no ha sido aplicado
- **Total Aplicado**: Monto que ya ha sido aplicado a facturas
- **Aplicaciones Registradas**: Lista de facturas a las que se ha aplicado

---

## Aplicar Anticipo desde la Factura

### Paso 1: Abrir la Factura

1. Ir a **Contabilidad → Clientes → Facturas**
2. Abrir una factura de cliente publicada con saldo pendiente

### Paso 2: Verificar Anticipos Disponibles

Si el cliente tiene anticipos disponibles, aparecerá un **banner informativo** en la parte superior de la factura mostrando:
- Cantidad de anticipos disponibles
- Monto total disponible

### Paso 3: Abrir el Wizard de Aplicación

1. Hacer clic en el botón **"Aplicar Anticipo"** en el header de la factura
   - O hacer clic en **"Aplicar ahora"** en el banner informativo

### Paso 4: Seleccionar Anticipos a Aplicar

En el wizard que se abre:

1. **Revisar la información de la factura**:
   - Monto de factura
   - Saldo pendiente
   - Total a aplicar (se calcula automáticamente)

2. **Revisar los anticipos disponibles**:
   - Cada anticipo muestra:
     - Referencia del pago
     - Fecha del anticipo
     - Diario
     - Saldo disponible
     - Monto a aplicar (editable)

3. **Ajustar montos**:
   - Ingresar el monto a aplicar en cada anticipo
   - Usar el botón **"Máx"** para aplicar el máximo disponible
   - Usar el botón **"Limpiar"** para limpiar el monto

4. **Validar totales**:
   - El sistema muestra:
     - Total a aplicar
     - Saldo después de aplicar
     - Si el total excede el residual, aparecerá un mensaje de error

### Paso 5: Aplicar los Anticipos

1. Hacer clic en **"Aplicar Anticipos"**
2. El sistema:
   - Crea asientos de reclasificación automáticamente
   - Concilia las líneas de la factura
   - Registra la aplicación en el chatter
   - Actualiza los saldos disponibles

### Paso 6: Verificar la Aplicación

1. En la factura, ir a la pestaña **"Anticipos Aplicados"**
2. Ver el detalle de:
   - Total aplicado
   - Lista de anticipos aplicados
   - Asientos de reclasificación generados
   - Fecha y usuario que aplicó

---

## Aplicar Anticipo desde el Pago

Este método permite aplicar un anticipo específico a múltiples facturas del mismo cliente.

### Paso 1: Abrir el Anticipo

1. Ir a **Contabilidad → Clientes → Anticipos**
2. Abrir un anticipo con saldo disponible
3. Verificar que el estado sea "Publicado" o "Enviado"

### Paso 2: Abrir el Wizard

1. En el panel de resumen del anticipo, hacer clic en **"Aplicar a Facturas"**
2. El sistema busca automáticamente todas las facturas pendientes del cliente con la misma moneda

### Paso 3: Seleccionar Facturas y Montos

En el wizard:

1. **Revisar información del anticipo**:
   - Monto del anticipo
   - Saldo disponible
   - Cliente

2. **Revisar facturas pendientes**:
   - Lista ordenada por fecha (más antiguas primero)
   - Cada factura muestra:
     - Número de factura
     - Fecha
     - Total
     - Saldo pendiente
     - Máximo aplicable (menor entre saldo del anticipo y residual de factura)
     - Monto a aplicar (editable)

3. **Distribuir el anticipo**:
   - Ingresar el monto a aplicar en cada factura
   - El sistema valida que no se exceda el saldo disponible del anticipo
   - El sistema valida que no se exceda el residual de cada factura

### Paso 4: Aplicar

1. Hacer clic en **"Aplicar a Facturas"**
2. El sistema procesa cada factura:
   - Crea asiento de reclasificación
   - Concilia líneas
   - Registra en chatter

---

## Consultar Anticipos

### Ver Todos los Anticipos

1. Ir a **Contabilidad → Clientes → Anticipos**
2. Ver lista de todos los anticipos registrados

### Filtros Disponibles

En la vista de búsqueda:
- **Anticipos**: Muestra todos los anticipos
- **Anticipos con saldo**: Solo anticipos que tienen saldo disponible
- **Anticipos aplicados**: Solo anticipos que ya tienen aplicaciones
- **Es Anticipo**: Agrupa por si es anticipo o no

### Columnas Disponibles

- **Es Anticipo**: Indica si es un anticipo
- **Saldo Disponible**: Monto disponible para aplicar
- **Total Aplicado**: Monto ya aplicado

### Ver Detalle de un Anticipo

1. Abrir cualquier anticipo
2. En el panel **"Anticipo de Cliente"** ver:
   - Saldo disponible
   - Total aplicado
   - Lista de aplicaciones realizadas con:
     - Factura
     - Asiento de reclasificación
     - Monto aplicado
     - Estado (Aplicado/Revertido)
     - Fecha de aplicación
     - Usuario que aplicó

---

## Ver Aplicaciones de Anticipos

### Acceder al Menú

1. Ir a **Contabilidad → Clientes → Aplicaciones de Anticipos**
2. Ver lista de todas las aplicaciones realizadas

### Filtros Disponibles

- **Aplicados**: Solo aplicaciones activas
- **Revertidos**: Solo aplicaciones que fueron revertidas

### Agrupaciones Disponibles

- **Cliente**: Agrupa por cliente
- **Anticipo**: Agrupa por anticipo
- **Factura**: Agrupa por factura
- **Estado**: Agrupa por estado (aplicado/revertido)
- **Fecha de aplicación**: Agrupa por mes

### Información Mostrada

- Anticipo aplicado
- Factura
- Monto aplicado
- Estado
- Asiento de reclasificación
- Fecha de aplicación
- Usuario que aplicó

### Acciones Disponibles

Desde cada aplicación se puede:
- Ver el anticipo original
- Ver la factura
- Ver el asiento de reclasificación

---

## Cancelar Factura con Anticipo Aplicado

### Proceso Automático

Cuando se cancela una factura que tiene anticipos aplicados:

1. El sistema **detecta automáticamente** las aplicaciones
2. Crea **asientos reversos** de las reclasificaciones
3. **Actualiza el estado** de los enlaces a "Revertido"
4. **Libera el saldo** del anticipo (vuelve a estar disponible)
5. **Registra en chatter** la reversión

### Pasos Manuales

1. Abrir la factura a cancelar
2. Verificar que tenga anticipos aplicados (pestaña "Anticipos Aplicados")
3. Hacer clic en **"Cancelar"**
4. Confirmar la cancelación
5. El sistema procesa automáticamente la reversión

### Verificar la Reversión

1. En el anticipo original, ver que el saldo disponible aumentó
2. En "Aplicaciones de Anticipos", ver que el estado cambió a "Revertido"
3. En el asiento de reclasificación, ver el asiento reverso creado

---

## Casos de Uso Comunes

### Caso 1: Cliente Paga Anticipo y Luego Factura

**Escenario**: Un cliente paga $1,000 como anticipo antes de recibir la factura.

**Pasos**:
1. Registrar el anticipo de $1,000
2. Cuando se factura, aplicar el anticipo desde la factura
3. La factura queda pagada automáticamente

### Caso 2: Anticipo Mayor que la Factura

**Escenario**: Cliente tiene un anticipo de $1,500 y se factura $1,000.

**Pasos**:
1. Aplicar $1,000 del anticipo a la factura
2. El anticipo queda con $500 de saldo disponible
3. Este saldo puede aplicarse a futuras facturas

### Caso 3: Múltiples Facturas con un Anticipo

**Escenario**: Cliente tiene un anticipo de $2,000 y se emiten 3 facturas de $800 cada una.

**Pasos**:
1. Desde el anticipo, hacer clic en "Aplicar a Facturas"
2. Distribuir el anticipo:
   - Factura 1: $800
   - Factura 2: $800
   - Factura 3: $400 (parcial)
3. El anticipo queda con $0 de saldo
4. La factura 3 queda con $400 pendientes

### Caso 4: Cancelar Factura con Anticipo

**Escenario**: Se cancela una factura que tenía un anticipo aplicado.

**Pasos**:
1. Cancelar la factura normalmente
2. El sistema revierte automáticamente la aplicación
3. El anticipo vuelve a estar disponible

### Caso 5: Anticipos en Diferentes Monedas

**Escenario**: Cliente tiene anticipos en USD y Lempiras.

**Comportamiento**:
- El sistema solo muestra anticipos en la misma moneda que la factura
- Los anticipos en otras monedas no aparecen como disponibles
- Esto evita errores de conversión

---

## Preguntas Frecuentes

### ¿Qué pasa si aplico más del saldo disponible?

El sistema **no permite** aplicar más del saldo disponible del anticipo. Mostrará un error de validación.

### ¿Qué pasa si aplico más del residual de la factura?

El sistema **no permite** aplicar más del saldo pendiente de la factura. Mostrará un error de validación.

### ¿Puedo aplicar un anticipo parcialmente?

Sí, siempre que la configuración lo permita. Puedes aplicar cualquier monto menor o igual al saldo disponible.

### ¿Qué pasa si cancelo una factura con anticipo aplicado?

El sistema **revierte automáticamente** la aplicación:
- Crea asiento reverso
- Libera el saldo del anticipo
- Marca la aplicación como revertida (no la elimina para mantener historial)

### ¿Puedo aplicar múltiples anticipos a una factura?

Sí, puedes aplicar varios anticipos a la misma factura. El wizard muestra todos los anticipos disponibles y puedes seleccionar cuánto aplicar de cada uno.

### ¿Los anticipos se aplican automáticamente?

No, debes aplicarlos manualmente usando el wizard. Esto te da control sobre cuánto aplicar y cuándo.

### ¿Qué cuenta contable se usa para los anticipos?

Se usa la cuenta configurada en "Cuenta de Anticipo por Defecto" en los ajustes. Esta cuenta debe ser:
- Pasivo Corriente
- Conciliable
- De la misma compañía

### ¿Puedo cambiar la cuenta de anticipo después de registrar el pago?

Sí, puedes cambiar la cuenta antes de validar el pago. Una vez validado, no se puede cambiar directamente (deberías cancelar y recrear).

### ¿Cómo veo el historial de aplicaciones?

Ve a **Contabilidad → Clientes → Aplicaciones de Anticipos** para ver todas las aplicaciones realizadas, incluyendo las revertidas.

### ¿Qué pasa si el cliente tiene anticipos en diferentes monedas?

Solo se muestran los anticipos en la misma moneda que la factura. Los anticipos en otras monedas no aparecen como disponibles.

### ¿Puedo aplicar un anticipo a una factura de otro cliente?

No, el sistema solo permite aplicar anticipos al mismo cliente. Valida automáticamente que el cliente coincida.

### ¿Cómo funciona la conciliación automática?

Cuando aplicas un anticipo:
1. Se crea un asiento de reclasificación
2. La línea de crédito (AR) del asiento se concilia automáticamente con la línea de débito (AR) de la factura
3. Si la conciliación automática falla, el sistema intenta una conciliación parcial manual

### ¿Qué información se registra en el chatter?

Se registra:
- Cuando se registra un anticipo
- Cuando se aplica a una factura (con monto y asiento)
- Cuando se revierte una aplicación

---

## Consejos y Mejores Prácticas

1. **Configurar correctamente la cuenta de anticipo**: Asegúrate de usar una cuenta de pasivo corriente conciliable.

2. **Revisar saldos antes de aplicar**: Siempre verifica que el anticipo tenga saldo disponible antes de intentar aplicarlo.

3. **Usar referencias descriptivas**: Al registrar anticipos, usa referencias claras (ej: "Anticipo Factura #12345") para facilitar el seguimiento.

4. **Revisar aplicaciones regularmente**: Revisa periódicamente las aplicaciones de anticipos para detectar inconsistencias.

5. **Documentar cancelaciones**: Si cancelas una factura con anticipo, documenta el motivo en el chatter.

6. **Monitorear anticipos antiguos**: Revisa periódicamente anticipos con saldo disponible que no se han aplicado en mucho tiempo.

7. **Usar filtros**: Aprovecha los filtros de búsqueda para encontrar rápidamente anticipos con saldo o aplicados.

---

## Soporte Técnico

Para soporte técnico o reportar problemas:
- Contactar al equipo de desarrollo
- Incluir capturas de pantalla del error
- Especificar los pasos para reproducir el problema

---

**Versión del Manual**: 2.0  
**Fecha de Actualización**: Enero 2026  
**Módulo**: gts_customer_advance v19.0.2.0.0
