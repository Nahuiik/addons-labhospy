# GTS COA Hierarchy

## Descripción

El módulo **GTS COA Hierarchy** extiende la funcionalidad del Plan de Cuentas (Chart of Accounts) de Odoo para permitir la creación de una jerarquía completa de cuentas contables con relaciones padre-hijo. Este módulo facilita la organización y consolidación de cuentas contables en estructuras jerárquicas complejas.

## Características Principales

### 1. Jerarquía de Cuentas
- **Relaciones Padre-Hijo**: Permite crear cuentas padre y cuentas hijas para organizar el plan de cuentas de manera jerárquica
- **Niveles de Cuenta**: Calcula automáticamente el nivel de profundidad de cada cuenta en la jerarquía
- **Validación de Ciclos**: Previene la creación de referencias circulares entre cuentas padre e hijas

### 2. Consolidación de Balances
- **Cálculo Automático**: Calcula automáticamente los balances consolidados de las cuentas padre incluyendo todas sus cuentas hijas
- **Múltiples Campos de Balance**:
  - Débito
  - Crédito
  - Balance
  - Balance de Apertura
  - Balance de Cierre
- **Filtros por Fecha**: Soporta filtros por rango de fechas para cálculos históricos
- **Filtros por Estado**: Permite filtrar por estado de los asientos contables

### 3. Tipos de Cuenta
- **Cuentas Vista (View)**: Cuentas que no pueden tener movimientos contables, solo sirven para agrupar otras cuentas
- **Tipos Personalizados**: Mantiene un campo personalizado de tipo de cuenta para propósitos de jerarquía
- **Tipos Disponibles**:
  - Vista (View)
  - Regular (Regular)
  - Por Cobrar (Receivable)
  - Por Pagar (Payable)
  - Liquidez (Liquidity)
  - Consolidación (Consolidation)
  - Cerrada (Closed)
  - Banco (Bank)

### 4. Conversión de Moneda
- Soporte para conversión automática de monedas cuando las cuentas hijas tienen diferentes monedas que la cuenta padre
- Utiliza el método moderno `_convert` de Odoo para conversiones precisas

### 5. Optimización de Rendimiento
- Utiliza `parent_path` para cálculos eficientes de jerarquía
- Implementa `_read_group` para cálculos de balance optimizados
- Almacena el nivel de cuenta para evitar cálculos repetitivos

## Instalación

1. Copia el módulo en la carpeta de addons de Odoo
2. Actualiza la lista de aplicaciones
3. Instala el módulo desde el menú de Aplicaciones

## Uso

### Crear una Cuenta Padre

1. Ve a **Contabilidad → Configuración → Plan de Cuentas**
2. Crea una nueva cuenta
3. Selecciona el tipo de cuenta como **"Vista"** (View)
4. Esta cuenta puede tener cuentas hijas pero no puede tener movimientos contables

### Crear una Cuenta Hija

1. Crea una nueva cuenta normalmente
2. En el campo **"Cuenta Padre"**, selecciona la cuenta padre deseada
3. El nivel de la cuenta se calculará automáticamente

### Ver Balances Consolidados

Los balances consolidados se calculan automáticamente y se muestran en:
- Vista de lista de cuentas
- Vista de formulario de cuenta
- Los balances incluyen todas las cuentas hijas y nietas recursivamente

## Campos Principales

- **parent_id**: Cuenta padre de la cuenta actual
- **parent_path**: Ruta jerárquica completa (usado internamente para optimización)
- **level**: Nivel de profundidad en la jerarquía (calculado automáticamente)
- **child_parent_ids**: Relación One2many con las cuentas hijas directas
- **debit**: Total de débitos consolidados
- **credit**: Total de créditos consolidados
- **balance**: Balance consolidado (débito - crédito)
- **opening_balance**: Balance de apertura consolidado
- **closing_balance**: Balance de cierre consolidado

## Requisitos

- Odoo 19.0 o superior
- Módulo `account` (incluido por defecto)

## Compatibilidad

Este módulo está diseñado específicamente para Odoo 19.0 y utiliza las características modernas de la plataforma:
- Usa `self.env.context` en lugar de `self._context` (deprecado)
- Compatible con el nuevo sistema de tipos de cuenta de Odoo 19
- Utiliza métodos modernos de conversión de moneda

## Autor

**Geo Technosoft Solutions Pvt Ltd.**
- Website: http://www.geotechnosoft.com

## Licencia

OPL-1 (Odoo Proprietary License v1.0)

## Versión

19.0.1.0.0

## Soporte

Para soporte técnico, contacta a Geo Technosoft Solutions.

## Notas Técnicas

- El módulo incluye un hook `post_init_hook` que inicializa el campo `parent_path` para registros existentes
- Los cálculos de balance respetan los filtros de fecha y estado del contexto
- La validación de ciclos previene recursión infinita limitando a 100 niveles
- Los cálculos de balance excluyen automáticamente los tipos de línea de visualización (secciones, notas, subsecciones)


