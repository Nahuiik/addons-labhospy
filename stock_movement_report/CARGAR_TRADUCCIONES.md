# Instrucciones para Cargar Traducciones en Odoo.sh

## Problema
Los encabezados de columnas y botones aparecen en inglés en lugar de español después de desplegar el módulo en odoo.sh.

## Solución

### Opción 1: Desde la Interfaz de Odoo (Recomendado)

1. **Verificar idioma del usuario:**
   - Ir a: **Configuración > Usuarios y Compañías > Usuarios**
   - Abrir tu usuario
   - Verificar que el campo **Idioma** sea: `Español (Guatemala) / es_GT`
   - Si no lo es, cambiarlo y guardar

2. **Cargar traducciones:**
   - Ir a: **Configuración > Traducciones > Cargar traducción**
   - Seleccionar:
     - **Módulo:** `stock_movement_report`
     - **Idioma:** `Español (Guatemala) / es_GT`
     - **Tipo:** `Importar traducción`
   - Clic en **Cargar**

3. **Actualizar módulo:**
   - Ir a: **Aplicaciones**
   - Buscar: `Inventory Movement Report`
   - Clic en **Actualizar**

4. **Recargar la página** (Ctrl+F5 o Cmd+Shift+R)

### Opción 2: Desde Terminal SSH en Odoo.sh

1. **Conectarse por SSH a odoo.sh**

2. **Actualizar el módulo:**
```bash
odoo-bin -u stock_movement_report -d tu_base_de_datos --stop-after-init
```

3. **Regenerar traducciones:**
```bash
odoo-bin -d tu_base_de_datos --i18n-overwrite --modules=stock_movement_report --stop-after-init
```

4. **Reiniciar el servicio** (si es necesario)

### Opción 3: Verificar que el archivo .po esté en el repositorio

Asegúrate de que el archivo `i18n/es_GT.po` esté incluido en el commit y se haya hecho push a odoo.sh:

```bash
git log --oneline -1 --name-only | grep es_GT.po
```

## Campos que deben traducirse

Los siguientes campos deben aparecer en español:

- **Print Preview** → **Vista Previa de Impresión**
- **Export (XLSX)** → **Exportar (XLSX)**
- **Internal Reference** → **Referencia Interna**
- **Product** → **Producto**
- **Opening Qty** → **Cantidad Inicial**
- **Qty In** → **Cantidad Entrada**
- **Qty Out** → **Cantidad Salida**
- **Closing Qty** → **Cantidad Final**
- **Opening Value** → **Valor Inicial**
- **Value In** → **Valor Entrada**
- **Value Out** → **Valor Salida**
- **Closing Value** → **Valor Final**

## Notas

- Si después de seguir estos pasos los campos siguen en inglés, verifica que:
  1. El archivo `i18n/es_GT.po` esté presente en el repositorio
  2. El módulo se haya actualizado correctamente
  3. El idioma del usuario esté configurado como `es_GT`
  4. La caché del navegador esté limpia
