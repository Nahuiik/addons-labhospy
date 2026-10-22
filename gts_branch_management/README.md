# GTS Branch Management

## Descripción

**GTS Branch Management** es un módulo de Odoo 19 que permite gestionar múltiples sucursales o múltiples unidades operativas dentro de una sola compañía. Este módulo extiende la funcionalidad de Odoo para trabajar con conceptos de múltiples sucursales de manera similar al entorno multi-compañía, pero dentro de una misma entidad legal.

## Características Principales

### 🔹 Gestión de Sucursales
- **Múltiples Sucursales**: Crea y gestiona múltiples sucursales dentro de una sola compañía
- **Código de Sucursal**: Sistema de referencia único para cada sucursal
- **Información Completa**: Dirección, teléfono, estado, GSTIN y más
- **Sucursal Principal**: Marca una sucursal como principal

### 🔹 Integración con Módulos Core
- **Órdenes de Venta**: Asignación automática de sucursal en órdenes de venta
- **Órdenes de Compra**: Gestión de sucursal en órdenes de compra
- **Facturas**: Asignación de sucursal en facturas y notas de crédito
- **Pagos**: Control de sucursal en pagos y recibos
- **Almacenes**: Vinculación de almacenes con sucursales
- **Ubicaciones de Stock**: Control de sucursal en ubicaciones de inventario
- **Transferencias**: Asignación automática de sucursal en transferencias

### 🔹 Diarios y Secuencias
- **Diarios por Sucursal**: Configuración de diarios de venta y compra por sucursal
- **Secuencias Personalizadas**: Secuencias de numeración independientes por sucursal
- **Diario por Defecto**: Configuración de diario predeterminado por usuario

### 🔹 Términos y Condiciones
- **Términos por Tipo de Documento**: 
  - Cotización/Orden
  - Factura
  - Proforma
  - Orden de Compra
- **Personalización**: Cada sucursal puede tener sus propios términos y condiciones

### 🔹 Plantillas PDF y Marcas de Agua
- **Plantilla de Factura**: PDF personalizado con marca de agua por sucursal
- **Plantilla de Cotización**: PDF personalizado para cotizaciones
- **Marcas de Agua**: Sistema de marcas de agua para documentos impresos
- **Última Página Personalizada**: Página final personalizada en documentos PDF

### 🔹 Control de Acceso
- **Usuario de Sucursal**: Los usuarios pueden estar asignados a una sucursal específica
- **Múltiples Sucursales**: Los usuarios pueden tener acceso a múltiples sucursales
- **Filtrado Automático**: Los usuarios solo ven registros de sus sucursales asignadas
- **Gerente de Sucursal**: Rol que permite ver todas las sucursales

### 🔹 Reportes Contables
- **Filtro por Sucursal**: Filtrado de reportes contables por sucursal
- **Análisis por Sucursal**: Agrupación y análisis de datos por sucursal
- **Reportes de Diario**: Filtrado de reportes de diario por sucursal

## Requisitos

- **Odoo**: Versión 19.0 o superior
- **Dependencias**: 
  - `base` (módulo base de Odoo)
  - `sale` y `sale_management` (Ventas)
  - `purchase` (Compras)
  - `stock` (Inventario)
  - `account` (Contabilidad)
  - `professional_templates` (Plantillas profesionales)

## Instalación

1. Copia el módulo en tu directorio de addons:
   ```bash
   cp -r gts_branch_management /ruta/a/tus/addons/
   ```

2. Actualiza la lista de aplicaciones en Odoo:
   - Ve a **Aplicaciones**
   - Haz clic en **Actualizar lista de aplicaciones**

3. Busca "GTS Branch Management" en las aplicaciones

4. Haz clic en **Instalar**

## Uso

### Crear una Sucursal

1. Ve a **Configuración > Usuarios y Compañías > Sucursales**
2. Haz clic en **Crear**
3. Completa la información:
   - **Código/Referencia de Sucursal**: Código único (requerido)
   - **Nombre**: Nombre de la sucursal (requerido)
   - **Compañía**: Selecciona la compañía (requerido)
   - **Dirección**: Dirección completa de la sucursal
   - **Teléfono**: Número de teléfono
   - **Estado**: Estado o provincia
   - **GSTIN**: Número de identificación fiscal si aplica
4. Configura los diarios:
   - **Diario**: Diario de ventas para esta sucursal
   - **Diario de Compras**: Diario de compras para esta sucursal
5. Configura las secuencias:
   - **Secuencia de Venta**: Secuencia para órdenes de venta
   - **Secuencia de Compra**: Secuencia para órdenes de compra
6. Configura términos y condiciones según el tipo de documento
7. Guarda la sucursal

### Asignar Sucursal a Usuario

1. Ve a **Configuración > Usuarios y Compañías > Usuarios**
2. Selecciona el usuario
3. En la pestaña **Sucursales**:
   - **Sucursal**: Sucursal principal del usuario
   - **Sucursales Permitidas**: Múltiples sucursales a las que tiene acceso
   - **Diario**: Diario por defecto del usuario

### Crear Almacén con Sucursal

1. Ve a **Inventario > Configuración > Almacenes**
2. Crea o edita un almacén
3. Selecciona la **Sucursal** correspondiente
4. Las ubicaciones del almacén heredarán automáticamente la sucursal

### Usar Sucursal en Documentos

- **Órdenes de Venta**: La sucursal se asigna automáticamente según el usuario, o se puede seleccionar manualmente
- **Órdenes de Compra**: Similar a órdenes de venta
- **Facturas**: La sucursal se hereda de la orden relacionada o se puede seleccionar
- **Pagos**: La sucursal se asigna automáticamente según el usuario

## Estructura del Módulo

```
gts_branch_management/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── res_branch.py              # Modelo principal de sucursal
│   ├── res_users.py               # Extensión de usuarios
│   ├── sale_order.py              # Órdenes de venta
│   ├── purchase_order.py          # Órdenes de compra
│   ├── account_move.py            # Facturas
│   ├── account_payment.py         # Pagos
│   ├── stock_warehouse.py         # Almacenes
│   ├── stock_location.py          # Ubicaciones
│   ├── stock_picking.py           # Transferencias
│   ├── account_bank_statement.py  # Extractos bancarios
│   └── report.py                  # Reportes PDF con marcas de agua
├── views/
│   ├── res_branch_views.xml       # Vistas de sucursal
│   ├── res_users.xml              # Vistas de usuario
│   ├── sale_order.xml             # Vistas de orden de venta
│   ├── purchase_order.xml         # Vistas de orden de compra
│   ├── account_move.xml           # Vistas de factura
│   └── stock_*.xml                # Vistas de inventario
├── wizard/
│   ├── account_common_report.py  # Wizard de reportes contables
│   └── account_common_report_wizard.xml
├── report/
│   └── account_analysis_report.xml
├── security/
│   ├── security.xml               # Reglas de seguridad
│   └── ir.model.access.csv        # Permisos de acceso
└── i18n/
    └── es_GT.po                   # Traducción al español (Guatemala)
```

## Campos Agregados

### res.branch (Sucursal)

- **branch_code**: Código/Referencia de la sucursal
- **name**: Nombre de la sucursal
- **address**: Dirección completa
- **telephone_no**: Número de teléfono
- **gst_no**: Número GSTIN
- **state_id**: Estado/Provincia
- **company_id**: Compañía
- **term_conditions**: Términos para cotizaciones/órdenes
- **term_conditions1**: Términos para facturas
- **term_conditions_proforma**: Términos para proformas
- **term_conditions_purchase**: Términos para órdenes de compra
- **journal_id**: Diario de ventas
- **purchase_journal_id**: Diario de compras
- **principal**: Indicador de sucursal principal
- **pdf_watermark_branch**: Plantilla PDF para facturas
- **pdf_watermark_branch_order**: Plantilla PDF para cotizaciones
- **sale_sequence_id**: Secuencia para órdenes de venta
- **purchase_sequence_id**: Secuencia para órdenes de compra

### res.users (Usuarios)

- **branch_id**: Sucursal principal del usuario
- **branch_ids**: Múltiples sucursales permitidas
- **journal_default_id**: Diario por defecto del usuario

### Documentos (sale.order, purchase.order, account.move, etc.)

- **branch_id**: Sucursal asignada al documento

## Funcionalidades Técnicas

### Asignación Automática de Sucursal

- Los documentos heredan la sucursal del usuario actual
- Se puede cambiar manualmente si el usuario tiene acceso a múltiples sucursales
- La sucursal se propaga automáticamente a documentos relacionados

### Validaciones

- **Ubicaciones**: Las ubicaciones deben tener la misma sucursal que el almacén relacionado
- **Almacenes**: Los almacenes deben tener sucursal asignada
- **Diarios**: Validación de diarios configurados para la sucursal seleccionada

### Secuencias Personalizadas

- Cada sucursal puede tener sus propias secuencias de numeración
- Si no hay secuencia en la sucursal, se usa la secuencia global del módulo
- Soporte para fechas en secuencias

### Marcas de Agua PDF

- Prioridad: Sucursal > Reporte > Compañía
- Soporte para PDFs con restricciones de seguridad
- Conversión automática de imágenes a PDF
- Validación de páginas y formato

## Traducciones

El módulo incluye traducción completa al español de Guatemala (`i18n/es_GT.po`). Para aplicar las traducciones:

1. Actualiza el módulo desde Aplicaciones
2. Ve a **Configuración > Traducciones > Cargar una traducción**
3. Selecciona idioma: **Español (Guatemala) / es_GT**
4. Selecciona módulo: **gts_branch_management**
5. Haz clic en **Cargar**

## Soporte y Contacto

- **Autor**: Geo Technosoft
- **Sitio Web**: https://www.geotechnosoft.com
- **Video Demo**: https://youtu.be/KN-fGNWOTTU
- **Licencia**: OPL-1 (Odoo Proprietary License v1.0)

## Versión

- **Versión Actual**: 19.0.1.0.0
- **Compatible con**: Odoo 19.0

## Notas de Desarrollo

### Grupos de Seguridad

El módulo incluye grupos de seguridad para:
- **Usuario de Sucursal**: Acceso limitado a su sucursal
- **Gerente de Sucursal**: Acceso a todas las sucursales

### Integración con professional_templates

El módulo requiere `professional_templates` para funcionalidades avanzadas de reportes PDF y marcas de agua.

## Changelog

### Versión 19.0.1.0.0
- Adaptación para Odoo 19
- Mejoras en asignación automática de sucursal
- Soporte mejorado para secuencias personalizadas
- Traducción completa al español (Guatemala)
- Integración mejorada con módulos de inventario

## Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Crea un fork del repositorio
2. Crea una rama para tu característica
3. Realiza tus cambios
4. Envía un pull request

---

**Desarrollado con ❤️ por Geo Technosoft**





