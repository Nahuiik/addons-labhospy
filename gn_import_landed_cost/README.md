# gn_import_landed_cost

**Costos en destino por picking (importación)**
Módulo Odoo 19 · Versión `19.0.1.0.0` · Autor: Grupo Nahuiik

Extiende el flujo de costos en destino
(`stock_landed_costs` + `invoice_in_landed_cost`) para compras
internacionales de LABHOSPY:

- **Dividir en dos recepciones planificadas** una orden de compra
  internacional (asistente con cantidades por línea).
- **Registrar gastos adicionales por picking** (permisos de importación,
  derechos arancelarios, impuesto por producción, u otros con
  `landed_cost_ok`) que **solo afectan a los productos de esa recepción**.
- Al calcular el costeo, las líneas globales siguen prorrateándose entre
  todos los pickings del `stock.landed.cost`; las líneas con alcance
  _"Solo esta recepción"_ únicamente reparten sobre los movimientos del
  picking indicado.

Consulte [`doc/MANUAL_USUARIO.md`](doc/MANUAL_USUARIO.md) para el manual
operativo detallado con capturas conceptuales, ejemplos numéricos y
solución de problemas.

## Instalación

Depende de `stock_landed_costs`, `purchase_stock`, `invoice_in_landed_cost`
y `gn_labhospy`.

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY -i gn_import_landed_cost --stop-after-init
```

Para actualizar tras cambios:

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY -u gn_import_landed_cost --stop-after-init
```

## Flujo operativo (resumen)

1. Crear OC marcada **Compra internacional** y confirmarla.
2. Presionar **Dividir recepción en dos** en la cabecera y asignar
   cantidades por línea a _Recepción 1_ y _Recepción 2_.
3. Validar cada recepción y capturar los gastos adicionales en la
   pestaña **Gastos adicionales importación** del picking.
4. Presionar **Sincronizar con costo en destino** para crear (o
   reutilizar) un `stock.landed.cost` con las líneas etiquetadas por
   picking.
5. Agregar los gastos generales (flete, seguro, etc.) desde las facturas
   de proveedor con `invoice_in_landed_cost` con alcance
   **Toda la importación**.
6. **Calcular** y **Validar** el costo en destino.

## Modelo de datos

| Modelo | Cambio principal |
|---|---|
| `stock.landed.cost.lines` | Campos `expense_scope`, `picking_id` |
| `stock.landed.cost` | Override de `compute_landed_cost` para prorrateo por scope |
| `stock.picking` | One2many `gn_import_extra_cost_line_ids`, flags `gn_import_reception_split` / `gn_import_reception_part`, botón sincronizar |
| `gn.import.extra.cost.line` | Modelo nuevo: tipo, producto, monto, método de reparto, factura |
| `purchase.order` | Botón "Dividir recepción en dos" |
| `purchase.split.reception.wizard` | Wizard con líneas por movimiento y cantidades por picking |

## Catálogo de productos (data)

| Producto | Código | Alcance sugerido |
|---|---|---|
| Permisos de importación | `LC_PERMISO_IMP` | Por picking |
| Derechos arancelarios | `LC_DERECHO_ARAN` | Por picking |
| Impuesto por producción | `LC_IMP_PROD` | Por picking |

Los tres son `product.product` tipo servicio con `landed_cost_ok=True` y
`split_method_landed_cost='by_quantity'`.

## Pruebas

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY -u gn_import_landed_cost --stop-after-init \
  --test-enable --test-tags gn_import_landed_cost --http-port=0
```

Cubren:

- Wizard divide una recepción en dos pickings preservando cantidades.
- Reparto híbrido: gasto global (por cantidad) + gasto por picking sobre
  un solo picking; verifica que el picking sin gasto no reciba el ajuste.

## Notas de implementación

- El wizard solo divide pickings en estado borrador o confirmado (no
  validados). Los backorders estándar de Odoo siguen funcionando.
- El override de `compute_landed_cost` solo se activa cuando alguna
  línea tiene `expense_scope='picking'`; en caso contrario delega en
  `invoice_in_landed_cost`.
- Compatible con `cancel_landed_cost_odoo` (revierte el costeo validado
  sin dependencias adicionales).
- Al sincronizar desde un picking se replica `amount` en
  `invoice_amount_lc` para evitar que la lógica USD/tasa de
  `invoice_in_landed_cost` recalcule `price_unit` a cero.
