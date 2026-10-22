# Módulo de Anticipos de Clientes para Odoo 19

## Descripción General

Este módulo permite gestionar anticipos de clientes en Odoo 19, registrando los pagos anticipados contra una cuenta de pasivo corriente conciliable y aplicándolos automáticamente a facturas del mismo cliente mediante una reclasificación contable de pasivo a cuentas por cobrar.

## Versión 2.0 - Optimizaciones

Esta versión incluye mejoras significativas de rendimiento, seguridad y funcionalidad:

### Optimizaciones de Rendimiento
- **Campo `advance_available_amount` almacenado**: Permite filtrar anticipos con saldo disponible directamente en SQL, evitando filtrados en Python
- **Cálculo optimizado de anticipos disponibles**: Agrupación por (partner, company, currency) para reducir consultas
- **Campos computed agrupados**: `_compute_has_available_advances` calcula múltiples campos en una sola pasada

### Mejoras de Seguridad
- **Reglas de registro multi-compañía**: Los usuarios solo ven los enlaces de anticipos de sus compañías
- **Permisos granulares**: Usuarios de contabilidad pueden aplicar anticipos, pero solo los asesores pueden modificar/eliminar

### Nuevas Funcionalidades
- **Aplicar desde el anticipo**: Nuevo botón en pagos para buscar y aplicar a múltiples facturas
- **Estado en enlaces**: Los enlaces ahora tienen estado (aplicado/revertido) para mejor trazabilidad
- **Filtros de búsqueda**: Filtros predefinidos para anticipos, anticipos con saldo, anticipos aplicados
- **Menú dedicado**: Nuevo menú "Anticipos" bajo Contabilidad > Clientes
- **Menú de aplicaciones**: Vista de todas las aplicaciones de anticipos realizadas

### Mejoras de UX
- **Banner mejorado**: Muestra cantidad de anticipos disponibles además del monto
- **Wizard mejorado**: Botones para aplicar máximo y limpiar montos
- **Vista de lista mejorada**: Columnas opcionales para anticipos en pagos y facturas

## Características Principales

### 1. Registro de Anticipos
- Checkbox "Es anticipo de cliente" en el formulario de pagos
- Campo obligatorio para seleccionar cuenta de anticipo (pasivo corriente conciliable)
- Tracking de cambios en campos importantes
- Validaciones automáticas:
  - La cuenta debe ser conciliable
  - Debe existir partner (cliente)
  - Solo disponible para pagos de clientes (inbound)

### 2. Detección de Anticipos en Facturas
- Banner informativo en facturas publicadas cuando hay anticipos disponibles
- Muestra cantidad y monto total de anticipos disponibles
- Botón "Aplicar Anticipo" para abrir el wizard de aplicación
- Filtros de búsqueda para facturas con anticipos

### 3. Aplicación de Anticipos (desde Factura)
- Wizard interactivo para seleccionar y aplicar anticipos
- Listado de anticipos disponibles con información detallada
- Campos editables para monto a aplicar por cada anticipo
- Botones de acción rápida (máximo, limpiar)
- Validaciones:
  - No permitir aplicar más del saldo disponible del anticipo
  - No permitir aplicar más del residual de la factura
  - Validación de cuenta por cobrar del cliente

### 4. Aplicación de Anticipos (desde Pago)
- Nuevo wizard para aplicar un anticipo a múltiples facturas
- Lista de facturas pendientes del cliente ordenadas por fecha
- Flexibilidad para distribuir el anticipo entre varias facturas

### 5. Reclasificación Contable Automática
- Generación automática de asientos de reclasificación:
  - Débito: Anticipos de clientes (Pasivo)
  - Crédito: Cuentas por cobrar (AR)
- Conciliación automática entre la factura y el asiento de reclasificación
- Soporte multi-moneda con conversión automática

### 6. Trazabilidad
- Modelo `account.advance.link` para registrar todas las aplicaciones
- Estado de aplicación (aplicado/revertido)
- Registro en chatter de facturas y pagos
- Referencias cruzadas entre anticipos, facturas y asientos
- Campos de auditoría (fecha, usuario)

### 7. Reversión de Anticipos
- Reversión automática al cancelar factura
- Asiento reverso para deshacer la reclasificación
- Intento de desconciliación de líneas
- Estado actualizado a "revertido" (no se elimina para mantener historial)

### 8. Configuración
- Ajustes en Contabilidad → Configuración:
  - Cuenta de anticipo por defecto
  - Diario de reclasificación
  - Origen de fecha del asiento (fecha factura / fecha actual)
  - Permitir fraccionar anticipos

## Instalación

1. Copiar el módulo a la carpeta de addons de Odoo
2. Actualizar la lista de aplicaciones
3. Instalar el módulo "Customer Advance Payments"
4. Configurar los parámetros en Contabilidad → Configuración → Ajustes

## Uso

### Registrar un Anticipo

1. Ir a Contabilidad → Clientes → Anticipos (o Pagos)
2. Crear un nuevo pago de cliente (Receive Money)
3. Marcar el checkbox "Es anticipo de cliente"
4. Seleccionar la cuenta de anticipo (si no está configurada, usar la cuenta por defecto)
5. Completar los demás campos del pago y validar

### Aplicar un Anticipo a una Factura (desde la Factura)

1. Abrir una factura de cliente publicada
2. Si hay anticipos disponibles, aparecerá un banner informativo
3. Hacer clic en "Aplicar Anticipo"
4. En el wizard, revisar los anticipos disponibles
5. Ajustar los montos a aplicar si es necesario
6. Hacer clic en "Aplicar Anticipos"

### Aplicar un Anticipo a Facturas (desde el Pago)

1. Abrir un pago marcado como anticipo con saldo disponible
2. Hacer clic en "Aplicar a Facturas"
3. Seleccionar las facturas y montos a aplicar
4. Hacer clic en "Aplicar a Facturas"

### Ver Aplicaciones de Anticipos

1. Ir a Contabilidad → Clientes → Aplicaciones de Anticipos
2. Ver historial de todas las aplicaciones realizadas
3. Filtrar por cliente, anticipo, factura o estado

### Cancelar una Factura con Anticipo Aplicado

Al cancelar una factura que tiene anticipos aplicados:
- Se crea automáticamente un asiento reverso de la reclasificación
- Se actualizan los estados de los enlaces a "revertido"
- El saldo del anticipo vuelve a estar disponible

## Flujo Contable

### Anticipo Recibido (1,000 USD)
```
Banco ......................... D  1,000
Anticipos de clientes (Pasivo) ... H  1,000 (con partner)
```

### Factura Emitida (1,000 USD)
```
CxC .......................... D  1,000 (partner)
Ingresos ..................... H  1,000
```

### Aplicación de Anticipo (Reclasificación)
```
Anticipos de clientes (Pasivo) ... D  1,000 (partner)
CxC .......................... H  1,000 (partner)
```

### Resultado
- La factura queda pagada (conciliada)
- El pasivo disminuye
- La compensación queda en AR (conciliada con la factura)

## Modelos de Datos

### account.payment
- `is_advance`: Boolean - Indica si es un anticipo (tracking)
- `advance_account_id`: Many2one - Cuenta de anticipo (tracking)
- `advance_available_amount`: Monetary - Saldo disponible (stored)
- `advance_applied_total`: Monetary - Total aplicado (stored)
- `advance_link_ids`: One2many - Aplicaciones realizadas

### account.move (Factura)
- `advance_applied_amount`: Monetary - Total aplicado (stored)
- `has_available_advances`: Boolean - Tiene anticipos disponibles
- `available_advances_amount`: Monetary - Monto disponible
- `available_advances_count`: Integer - Cantidad de anticipos disponibles
- `advance_link_ids`: One2many - Aplicaciones recibidas

### account.advance.link
- `payment_id`: Many2one - Anticipo aplicado (index)
- `move_id`: Many2one - Factura (index)
- `reclass_move_id`: Many2one - Asiento de reclasificación
- `amount`: Monetary - Monto aplicado
- `state`: Selection - Estado (applied/reversed)
- `partner_id`: Many2one - Cliente (stored, index)
- `company_id`: Many2one - Compañía (stored, index)
- `applied_date`: Datetime - Fecha de aplicación
- `applied_user_id`: Many2one - Usuario que aplicó
- `payment_date`: Date - Fecha del anticipo (related)
- `invoice_date`: Date - Fecha de factura (related)

## Seguridad

### Permisos por Grupo
| Grupo | account.advance.link | Wizards |
|-------|---------------------|---------|
| Usuario de Contabilidad | Solo lectura | Completo |
| Asesor de Contabilidad | Completo | Completo |

### Reglas de Registro
- **Multi-compañía**: Los usuarios solo ven enlaces de anticipos de sus compañías asignadas

## Consideraciones

- **Multi-moneda**: Se convierte automáticamente al aplicar anticipos con diferente moneda
- **Multi-compañía**: Los anticipos se filtran por compañía con reglas de registro
- **Impuestos**: El anticipo no genera impuestos; los impuestos se determinan en la factura
- **Rendimiento**: Campos almacenados permiten búsquedas eficientes en SQL
- **Reversión**: Los enlaces no se eliminan al revertir, se marca el estado para mantener historial

## Changelog

### v2.0.0
- Campo `advance_available_amount` almacenado para filtros SQL
- Reglas de registro multi-compañía
- Centralización de obtención de configuración
- Validaciones mejoradas (factura pagada, cuenta AR)
- Tracking en campos importantes
- Nuevo wizard para aplicar desde el pago
- Estado en enlaces (aplicado/revertido)
- Filtros de búsqueda en pagos y facturas
- Menú dedicado para anticipos
- Documentación completa con docstrings

### v1.0.0
- Versión inicial

## Soporte

Para soporte técnico, contactar a Geo Technosoft.

## Licencia

LGPL-3
