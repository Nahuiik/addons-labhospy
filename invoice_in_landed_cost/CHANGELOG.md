# Changelog - Invoice Landed Cost

## Versión 19.0.0.1 - 2026-01-05

### Nuevas Funcionalidades

1. **Reporte PDF de Costo en Destino**
   - Botón "Report Landed Cost" agregado al formulario
   - Reporte PDF con 3 secciones:
     - Costos adicionales: Detalle de todas las líneas de costo
     - Costos por Producto: Resumen agrupado por producto
     - Ajustes de valoración: Detalle de los ajustes aplicados

2. **Tab "Costos por Producto" en el Formulario**
   - Nuevo tab en el formulario de Costo en Destino
   - Vista tree que muestra resumen por producto:
     - Producto
     - Cantidad (con suma total)
     - Valor Original (con suma total, formato monetario)
     - Costo en Destino (con suma total, formato monetario)
     - Costo Final (con suma total, formato monetario)
   - Actualización automática al calcular los costos

3. **Traducciones al Español (Guatemala)**
   - Archivo de traducción `es_GT.po` creado
   - Todas las etiquetas y textos traducidos

### Cambios Técnicos

1. **Nuevo Modelo**: `landed.cost.product.summary`
   - Modelo transitorio para almacenar el resumen por producto
   - Se crea dinámicamente cuando se necesita

2. **Nuevo Campo**: `product_summary_ids` en `stock.landed.cost`
   - Campo computed One2many
   - Se actualiza automáticamente cuando cambian los `valuation_adjustment_lines`

3. **Nuevo Método**: `get_costs_by_product()` en `stock.landed.cost`
   - Agrupa los costos por producto
   - Retorna un diccionario con el resumen
   - Usado para el reporte PDF

4. **Corrección de Errores**:
   - Corregido acceso a `journal_id` usando `account_move_id.journal_id`
   - Mejorado el manejo de campos opcionales en el template del reporte

### Archivos Modificados

- `models/stock_landed_cost.py`: Agregado método `get_costs_by_product()` y campo `product_summary_ids`
- `models/landed_cost_product_summary.py`: Nuevo modelo transitorio
- `models/__init__.py`: Importación del nuevo modelo
- `views/stock_landed_cost.xml`: Agregado tab "Costos por Producto"
- `report/landed_cost_report.xml`: Nueva acción de reporte
- `report/landed_cost_report_templates.xml`: Template del reporte PDF
- `i18n/es_GT.po`: Traducciones al español
- `__manifest__.py`: Agregados archivos de reporte

### Instrucciones de Actualización

1. **Actualizar el módulo**:
   ```bash
   odoo-bin -u invoice_in_landed_cost -d tu_base_de_datos
   ```

2. **Cargar traducciones** (si es necesario):
   - Ir a Configuración → Traducciones → Cargar una traducción
   - Seleccionar idioma: Español (Guatemala) / es_GT
   - O actualizar el módulo con el idioma activado

3. **Verificar funcionalidad**:
   - Abrir un registro de "Costo en destino"
   - Verificar que aparece el tab "Costos por Producto"
   - Calcular los costos y verificar que el tab se actualiza
   - Hacer clic en "Report Landed Cost" y verificar que se genera el PDF

### Notas

- El modelo `landed.cost.product.summary` es transitorio y no requiere permisos especiales
- El campo `product_summary_ids` es computed y no se almacena en la base de datos
- El tab se actualiza automáticamente cuando se calculan los costos mediante `compute_landed_cost()`



## Versión 19.0.0.3 - 2026-04-15

### Nuevas funcionalidades

1. **Pestaña «Margen venta» y asistente de margen sobre PVP**
   - Tras calcular el costeo (líneas de valoración), se puede abrir un asistente que lista los productos afectados con costo unitario final.
   - Margen global (aplicar a todas las líneas) o margen por producto.
   - Al aplicar: actualiza `list_price` de la variante para alinear el PVP al costo × (1 + margen/100), respetando `price_extra`.
   - Mensajes en el chatter de la plantilla de producto y del costeo en destino, con referencia al costeo (secuencia/nombre).
   - Campo «Última aplicación margen venta» en el costeo.

2. **Informe PDF «Resumen margen venta (costeo)»**
   - Se abre al confirmar el asistente; muestra costo unitario, % margen, PVP anterior y PVP objetivo por línea.

3. **Reglas de negocio**
   - No se permite **eliminar** registros de costo en destino (`unlink` bloqueado).
   - No se permite **guardar** un costeo sin al menos una línea en «Costos adicionales» (validación; la sincronización desde facturas usa contexto interno para no romper la creación).

### Cambios técnicos

- Nuevos modelos transitorios: `landed.cost.sale.margin.wizard`, `landed.cost.sale.margin.wizard.line`.
- Extensión de `stock.landed.cost`: `margin_last_applied_on`, `action_open_sale_margin_wizard`, `_check_cost_lines_required`, `unlink` sobreescrito, `create` con validación post-sincronización de facturas.



