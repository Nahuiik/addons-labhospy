# Instrucciones para Diagnosticar el Problema

## 🔍 Problema Identificado

El módulo está instalado pero el modelo `stock.valuation.report` no está disponible. Esto significa que **el módulo necesita ser actualizado** para cargar los nuevos modelos.

## 📋 Pasos para Diagnosticar

### Paso 1: Verificar que el módulo esté actualizado

1. **Desde la interfaz web de Odoo:**
   - Ve a: **Aplicaciones**
   - Busca: **"Stock Inventory"** o **"deltatech_stock_inventory"**
   - Si aparece el botón **"Actualizar"**, haz clic en él
   - Espera a que termine la actualización

2. **O desde la línea de comandos:**
   ```bash
   cd /opt/odoo19
   python3 odoo/odoo-bin -d LAB19C -u deltatech_stock_inventory --stop-after-init
   ```

### Paso 2: Reiniciar el servidor de Odoo

Después de actualizar, **reinicia el servidor de Odoo** para que cargue los nuevos modelos.

### Paso 3: Ejecutar el diagnóstico

Ejecuta este comando para ver el diagnóstico completo:

```bash
/opt/odoo19/addons-odoo/deltatech_stock_inventory/diagnostico.sh
```

### Paso 4: Probar desde la interfaz

1. Ve a: **Inventario > Reportes > Inventory Valuation**
2. Selecciona fechas (From Date y To Date)
3. Haz clic en **"Compute"**
4. **Toma una captura de pantalla** de lo que ves

## 🔧 Información que Necesito

Por favor, proporciona:

1. **Resultado del diagnóstico:**
   ```bash
   /opt/odoo19/addons-odoo/deltatech_stock_inventory/diagnostico.sh > diagnostico.txt 2>&1
   cat diagnostico.txt
   ```

2. **Captura de pantalla** del reporte cuando lo abres

3. **Información del servidor:**
   - ¿El servidor de Odoo está corriendo?
   - ¿Cuándo fue la última vez que se reinició?
   - ¿Hay algún error en los logs del servidor?

4. **Verificar en la base de datos:**
   Ejecuta esto y compárteme el resultado:
   ```bash
   cd /opt/odoo19
   python3 odoo/odoo-bin shell -d LAB19C --no-http << 'EOF'
   # Verificar si el modelo existe
   if 'stock.valuation.report' in env:
       print("✓ Modelo disponible")
       # Crear un reporte de prueba
       company = env['res.company'].search([], limit=1)
       from odoo import fields
       from datetime import date, datetime
       report = env['stock.valuation.report'].create({
           'company_id': company.id,
           'date_to': fields.Datetime.now(),
       })
       print(f"Reporte creado: ID={report.id}")
       report._compute_valuation()
       print(f"Initial Balance: {report.initial_balance}")
       print(f"Ending Stock: {report.ending_stock}")
       print(f"Stock Variation: {report.stock_variation}")
   else:
       print("✗ Modelo NO disponible - módulo necesita actualización")
   EOF
   ```

## 🐛 Posibles Problemas y Soluciones

### Problema 1: El modelo no está disponible
**Solución:** Actualizar el módulo y reiniciar el servidor

### Problema 2: Los valores son 0 pero `stock_value()` devuelve datos
**Causa posible:** El método `_compute_valuation()` no se está ejecutando correctamente
**Solución:** Verificar los logs del servidor para ver si hay errores

### Problema 3: No se muestran datos en la interfaz
**Causa posible:** Los campos computed no se están calculando al abrir el formulario
**Solución:** Verificar que el método `create()` esté forzando el cálculo

### Problema 4: Error de permisos
**Solución:** Verificar que el usuario tenga los permisos correctos

## 📝 Checklist de Verificación

- [ ] Módulo `deltatech_stock_inventory` está instalado
- [ ] Módulo `stock_account` está instalado
- [ ] Módulo `account` está instalado
- [ ] El módulo ha sido actualizado después de los cambios
- [ ] El servidor de Odoo ha sido reiniciado
- [ ] El modelo `stock.valuation.report` está disponible
- [ ] El método `company.stock_value()` funciona y devuelve datos
- [ ] Hay productos almacenables en el sistema
- [ ] Los productos tienen cuentas de valuación configuradas
- [ ] Hay movimientos de inventario en el período seleccionado

## 🚀 Comandos Útiles

### Verificar estado del módulo:
```bash
cd /opt/odoo19
python3 odoo/odoo-bin shell -d LAB19C --no-http << 'EOF'
module = env['ir.module.module'].search([('name', '=', 'deltatech_stock_inventory')], limit=1)
print(f"Estado: {module.state}")
print(f"Última actualización: {module.write_date}")
EOF
```

### Verificar si el modelo está cargado:
```bash
cd /opt/odoo19
python3 odoo/odoo-bin shell -d LAB19C --no-http << 'EOF'
if 'stock.valuation.report' in env:
    print("✓ Modelo disponible")
else:
    print("✗ Modelo NO disponible")
EOF
```

### Ver logs del servidor:
```bash
# Buscar errores relacionados con stock.valuation.report
tail -f /var/log/odoo/odoo.log | grep -i "stock.valuation"
```

## 📞 Siguiente Paso

Una vez que tengas la información del diagnóstico, compártela conmigo y podré identificar exactamente qué está fallando y cómo solucionarlo.




