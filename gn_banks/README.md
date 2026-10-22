# Módulo de Bancos (gn_banks)

## Descripción

Este módulo permite registrar débito, crédito, depósitos, cheques y transferencias bancarias en Odoo. Incluye funcionalidades completas para la gestión de transacciones bancarias con soporte para contabilidad analítica.

## Características Principales

- **Gestión de Débitos y Créditos**: Registro y validación de transacciones de débito y crédito bancario
- **Gestión de Depósitos**: Registro de depósitos bancarios con soporte para anticipos de clientes
- **Gestión de Cheques**: Emisión y control de cheques bancarios
- **Transferencias Bancarias**: Registro de transferencias entre cuentas bancarias
- **Plantillas**: Sistema de plantillas para agilizar la creación de transacciones recurrentes
- **Contabilidad Analítica**: Soporte completo para distribución analítica en las líneas de transacciones
- **Reportes**: Generación de reportes en Excel para todos los tipos de transacciones

## Dependencias

- `base`
- `account`
- `mail`
- `analytic`

## Instalación

1. Copiar el módulo en la carpeta de addons de Odoo
2. Actualizar la lista de aplicaciones
3. Instalar el módulo desde la interfaz de Odoo

## Uso

### Transacciones Bancarias

El módulo permite crear diferentes tipos de transacciones bancarias:

- **Débito**: Registro de débitos bancarios
- **Crédito**: Registro de créditos bancarios
- **Depósito**: Registro de depósitos bancarios
- **Tarjeta de Crédito**: Liquidación de tarjetas de crédito
- **Cheques**: Emisión de cheques
- **Transferencias**: Transferencias entre bancos

### Contabilidad Analítica

Las transacciones bancarias incluyen soporte para contabilidad analítica:

- **Distribución Analítica**: Se puede asignar distribución analítica a cada línea de transacción
- **Precisión Analítica**: La precisión de los montos analíticos se calcula automáticamente basándose en la moneda de la compañía
- **Ubicación**: Los campos analíticos están disponibles únicamente en las líneas de transacción, no en el encabezado

### Plantillas

Las plantillas permiten guardar configuraciones de transacciones recurrentes para agilizar el proceso de registro.

## Cambios Recientes

### Versión 19.0.1.0.0

- **Mejoras en Contabilidad Analítica**:
  - Agregado campo `analytic_precision` a todos los modelos que utilizan distribución analítica
  - Los campos analíticos ahora están disponibles únicamente en las líneas de transacción
  - Eliminada la sección analítica del encabezado de los formularios
  - Mejorada la visualización de campos analíticos en las vistas de lista

- **Mejoras en la Interfaz**:
  - Eliminado el botón "Vista" de las líneas de transacción
  - Optimizada la visualización de campos analíticos en las listas

## Traducciones

El módulo incluye traducciones al español de Guatemala (es_GT).

## Autor

Grupo Nahuiik

## Licencia

OPL-1







