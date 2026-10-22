# GN Import Purchase Order Lines

Módulo para importar líneas de orden de compra masivamente desde archivos CSV o Excel.

## Características

- ✅ Importación masiva de líneas de compra
- ✅ Soporte para archivos CSV y Excel (.xls, .xlsx)
- ✅ Opciones para tomar detalles del producto o del archivo
- ✅ Importación por código, código de barras o nombre
- ✅ Validación de datos antes de importar
- ✅ Creación automática de productos (opcional)

## Instalación

### Requisitos

El módulo requiere las siguientes librerías Python para leer archivos Excel:

```bash
pip install xlrd
```

O en sistemas Ubuntu/Debian:

```bash
sudo apt-get install python-xlrd
```

### Instalación del módulo

1. Copiar el módulo a la carpeta de addons
2. Actualizar la lista de módulos en Odoo
3. Instalar el módulo "GN Import Purchase Order Lines"

## Uso

### Formato del archivo

El archivo CSV o Excel debe tener las siguientes columnas:

#### Columnas requeridas:
- **PRODUCT** (o CODE/BARCODE/NAME según la opción seleccionada): Identificador del producto
- **QUANTITY**: Cantidad a comprar

#### Columnas opcionales:
- **UOM**: Unidad de medida
- **PRICE**: Precio unitario
- **DESCRIPTION**: Descripción de la línea
- **TAX**: Impuestos (separados por coma si hay múltiples)

### Ejemplo de archivo CSV

```csv
PRODUCT,QUANTITY,UOM,PRICE,DESCRIPTION,TAX
PROD001,10,Unidades,25.50,Producto de ejemplo,IVA 13% Compras
PROD002,5,Unidades,15.00,Otro producto,
```

### Pasos para importar

1. Abrir una orden de compra
2. Hacer clic en el botón **"Importar Líneas"**
3. Seleccionar las opciones:
   - **Opción de Detalles del Producto**: 
     - Tomar detalles del producto: Usa UOM y precio del producto
     - Tomar detalles del archivo: Usa todos los datos del archivo
     - Tomar detalles con lista de precios: Usa precios de la lista de precios del proveedor
   - **Importar Producto Por**: Código, Código de Barras o Nombre
   - **Crear producto si no existe**: Solo disponible cuando se importa por nombre
4. Seleccionar el archivo CSV o Excel
5. Hacer clic en **"Importar"**

## Notas importantes

- Si usa valores numéricos para código o código de barras, asegúrese de que el formato de celda sea **Texto** en Excel
- Los impuestos deben existir previamente en el sistema
- Las unidades de medida deben existir previamente en el sistema
- Si un producto no existe y no está marcada la opción de crear productos, se mostrará un error

## Autor

Grupo Nahuiik

## Licencia

LGPL-3











