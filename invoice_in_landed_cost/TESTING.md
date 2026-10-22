# Pruebas Funcionales - Invoice Landed Cost

## Resumen de Funcionalidades Implementadas

1. **Reporte PDF de Costo en Destino**
   - Botón "Report Landed Cost" en el formulario
   - Reporte con 3 secciones: Costos adicionales, Costos por Producto, Ajustes de valoración

2. **Tab "Costos por Producto" en el Formulario**
   - Vista tree que muestra resumen por producto
   - Campos: Producto, Cantidad, Valor Original, Costo en Destino, Costo Final
   - Sumas totales en el pie de tabla

## Checklist de Pruebas

### 1. Instalación y Actualización del Módulo
- [ ] Actualizar el módulo `invoice_in_landed_cost`
- [ ] Verificar que no haya errores en el log durante la actualización
- [ ] Verificar que el modelo `landed.cost.product.summary` se crea correctamente

### 2. Pruebas del Formulario

#### 2.1. Visualización del Tab "Costos por Producto"
- [ ] Abrir un registro de "Costo en destino" existente
- [ ] Verificar que aparece el tab "Costos por Producto" en el notebook
- [ ] Verificar que el tab está después de "Ajustes de valoración"

#### 2.2. Contenido del Tab
- [ ] Verificar que se muestran las columnas: Producto, Cantidad, Valor Original, Costo en Destino, Costo Final
- [ ] Verificar que los valores monetarios se muestran con el formato correcto
- [ ] Verificar que aparecen las sumas totales en el pie de la tabla
- [ ] Verificar que los campos son de solo lectura

#### 2.3. Cálculo de Costos
- [ ] Crear un nuevo "Costo en destino"
- [ ] Agregar facturas de proveedor
- [ ] Agregar traslados
- [ ] Calcular los costos en destino (botón "Compute")
- [ ] Verificar que el tab "Costos por Producto" se actualiza automáticamente
- [ ] Verificar que los valores son correctos:
  - Cantidad: suma de cantidades por producto
  - Valor Original: suma de (former_cost * quantity) por producto
  - Costo en Destino: suma de (additional_landed_cost * quantity) por producto
  - Costo Final: suma de (final_cost * quantity) por producto

### 3. Pruebas del Reporte PDF

#### 3.1. Generación del Reporte
- [ ] Hacer clic en el botón "Report Landed Cost"
- [ ] Verificar que se genera el PDF sin errores
- [ ] Verificar que el PDF se abre correctamente

#### 3.2. Contenido del Reporte
- [ ] Verificar que aparece el título "Costo en destino: [número]"
- [ ] Verificar que aparece la fecha
- [ ] Verificar que aparece el diario (si existe account_move_id)
- [ ] Verificar que aparecen los traslados
- [ ] Verificar que aparecen las facturas de proveedor

#### 3.3. Sección "Costos adicionales"
- [ ] Verificar que se muestran todas las líneas de costos
- [ ] Verificar que aparecen todas las columnas
- [ ] Verificar que el total es correcto

#### 3.4. Sección "Costos por Producto"
- [ ] Verificar que aparece la sección "Costos por Producto"
- [ ] Verificar que se muestran los productos agrupados
- [ ] Verificar que los valores son correctos:
  - Cantidad total por producto
  - Valor Original total por producto
  - Costo en Destino total por producto
  - Costo Final total por producto
- [ ] Verificar que aparecen los totales en el pie de tabla

#### 3.5. Sección "Ajustes de valoración"
- [ ] Verificar que se muestran todas las líneas de ajuste
- [ ] Verificar que aparecen todas las columnas
- [ ] Verificar que los valores son correctos

### 4. Pruebas de Traducción

#### 4.1. Idioma Español (Guatemala)
- [ ] Configurar el idioma del usuario a Español (Guatemala)
- [ ] Actualizar las traducciones del módulo
- [ ] Verificar que todos los textos aparecen en español:
  - Botón "Reporte de Costo en Destino"
  - Tab "Costos por Producto"
  - Encabezados de columnas
  - Textos del reporte PDF

### 5. Pruebas de Casos Especiales

#### 5.1. Sin Productos
- [ ] Crear un costo en destino sin productos
- [ ] Verificar que el tab "Costos por Producto" está vacío o muestra mensaje apropiado

#### 5.2. Sin Ajustes de Valoración
- [ ] Crear un costo en destino sin calcular los costos
- [ ] Verificar que el tab "Costos por Producto" está vacío

#### 5.3. Múltiples Productos
- [ ] Crear un costo en destino con múltiples productos
- [ ] Verificar que todos los productos aparecen en el resumen
- [ ] Verificar que los totales son correctos

#### 5.4. Productos con Diferentes Cantidades
- [ ] Crear un costo en destino con productos que tienen diferentes cantidades
- [ ] Verificar que las cantidades se suman correctamente por producto

### 6. Pruebas de Rendimiento

- [ ] Probar con un costo en destino que tenga muchos productos (50+)
- [ ] Verificar que el tab se carga en tiempo razonable (< 2 segundos)
- [ ] Verificar que el reporte PDF se genera en tiempo razonable (< 5 segundos)

## Errores Conocidos y Soluciones

### Error: AttributeError: 'stock.landed.cost' object has no attribute 'journal_id'
**Solución**: Ya corregido. Se usa `account_move_id.journal_id` en lugar de `journal_id`.

### Error: El tab no se actualiza automáticamente
**Solución**: El campo computed tiene `@api.depends` en `valuation_adjustment_lines` y se actualiza cuando se calculan los costos.

## Notas de Implementación

1. El modelo `landed.cost.product.summary` es un modelo transitorio que se crea dinámicamente
2. El campo `product_summary_ids` es computed y no se almacena en la base de datos
3. El método `create_summary_lines()` elimina las líneas anteriores antes de crear nuevas
4. El método `get_costs_by_product()` se usa solo para el reporte PDF
5. El tab se actualiza automáticamente cuando se calculan los costos mediante `compute_landed_cost()`







