# Manual de Usuario — Costos en destino por picking (importación)

**Módulo:** `gn_import_landed_cost` · **Versión:** 19.0.1.0.0 · **Odoo:** 19 CE
**Autor:** Grupo Nahuiik · **Base de datos de referencia:** LABHOSPY

---

## 1. ¿Qué resuelve este módulo?

En LABHOSPY, una compra internacional puede llegar en **dos recepciones
distintas** (por ejemplo: un contenedor con equipos que llega en aduana
y otro con reactivos que sigue en tránsito). Cada recepción tiene sus
propios **permisos, aranceles e impuestos**, mientras que otros gastos
(flete, seguro, comisiones) sí se comparten entre ambas.

Con Odoo estándar más `invoice_in_landed_cost`, cuando un
`stock.landed.cost` incluye varios pickings **todos los gastos** se
prorratean entre **todos los productos** de todos los pickings
seleccionados. Este módulo agrega el concepto de **alcance del gasto**:

- **Toda la importación** (comportamiento actual): el gasto se reparte
  entre todos los productos de todas las recepciones del costeo.
- **Solo esta recepción**: el gasto se reparte únicamente entre los
  productos del picking indicado, **sumándose** al reparto de los gastos
  globales.

Adicionalmente entrega un **asistente para dividir una recepción
planificada** en dos pickings desde la orden de compra, sin depender del
backorder estándar de Odoo.

---

## 2. Acceso y permisos

- **Menú:** _Inventario → Operaciones → Transferencias_ (para pickings)
  y _Inventario → Operaciones → Costos en destino_ (para el costeo).
- **Acción en OC:** botón _Dividir recepción en dos_ en la cabecera de
  la orden de compra.
- **Permisos:** cualquier usuario con acceso a compras/inventario puede
  registrar gastos. **Validar** el costeo sigue requiriendo el grupo
  _Validar costos en destino_ (`invoice_in_landed_cost`).

No se agregan grupos nuevos.

---

## 3. Requisitos previos

Antes de usar el módulo, verifique:

1. La orden de compra tiene el checkbox **Compra internacional**
   (`gn_labhospy_compra_internacional`) activo. Este flag se define en
   `gn_labhospy` y ya existe en su instancia.
2. Los productos de la OC tienen `product.categ_id.property_cost_method`
   en **FIFO** o **Precio promedio** (el costeo en destino requiere
   valuación real).
3. Los productos servicio que utilice como gasto (permisos, aranceles,
   impuestos u otros) tienen `landed_cost_ok = True`. El módulo carga
   tres productos por defecto:

   | Producto | Código | Método de reparto por defecto |
   |---|---|---|
   | Permisos de importación | `LC_PERMISO_IMP` | Por cantidad |
   | Derechos arancelarios | `LC_DERECHO_ARAN` | Por cantidad |
   | Impuesto por producción | `LC_IMP_PROD` | Por cantidad |

---

## 4. Flujo completo (paso a paso)

### 4.1. Confirmar la orden de compra internacional

1. Cree la OC como de costumbre y marque **Compra internacional**.
2. Confirme la OC. Odoo genera automáticamente un picking de entrada en
   borrador con todas las líneas.

### 4.2. Dividir la recepción en dos pickings

1. En la OC confirmada aparece el botón **Dividir recepción en dos**
   (solo visible cuando existe un picking de entrada en borrador).
2. Al pulsarlo se abre el asistente
   _Dividir recepción en dos pickings_ con una fila por línea del
   picking:

   | Producto | UdM | Cantidad original | Recepción 1 | Recepción 2 | Diferencia |
   |---|---|---|---|---|---|
   | Reactivo A | Und | 100 | **80** | **20** | 0 |
   | Equipo B | Und | 5 | **0** | **5** | 0 |

3. Ajuste **Recepción 1** o **Recepción 2**; el otro campo se completa
   solo para que **Diferencia = 0** en cada línea. Si algún renglón
   queda con diferencia distinta de cero se marca en rojo y al confirmar
   se aborta con un mensaje.
4. Pulse **Confirmar división**. El módulo:
   - Ajusta la cantidad del movimiento original en el _Picking 1_.
   - Crea un _Picking 2_ nuevo (mismo `purchase_id`, mismo tipo de
     operación, ubicación destino y proveedor) con los movimientos
     restantes.
   - Marca ambos pickings con `gn_import_reception_split=True` y con
     `gn_import_reception_part` (`first` / `second`).

Notas importantes:

- El wizard es un flujo **planificado**. No reemplaza el backorder
  estándar (que sigue funcionando para partial receipts imprevistos).
- Puede volver a lanzar el wizard sobre el _Picking 1_ resultante si
  necesita más subdivisiones.

### 4.3. Validar cada recepción y capturar gastos por picking

Para cada picking (Recepción 1 y Recepción 2):

1. Valide la recepción con el flujo normal de Odoo
   (_Reservar_, _Validar_).
2. Abra el picking validado. En el bloc de notas verá la pestaña
   **Gastos adicionales importación** (solo aparece en recepciones
   entrantes que estén vinculadas a una `purchase.order`).
3. Registre una fila por gasto:

   | Tipo | Producto | Descripción | Monto | Método de reparto | Factura |
   |---|---|---|---|---|---|
   | Permisos de importación | (autoselecciona) | Permiso SAG lote 234 | 1200 | Por cantidad | (opcional) |
   | Derechos arancelarios | (autoselecciona) | DAI 15% | 4800 | Por cantidad | (opcional) |
   | Impuesto por producción | (autoselecciona) | Impuesto producción HN | 900 | Por cantidad | (opcional) |
   | Otro | (elija cualquiera con `landed_cost_ok`) | | ... | ... | ... |

   El campo **Producto** se autocompleta al elegir el **Tipo**; puede
   sobreescribirlo si su compañía usa otros artículos servicio.
4. Cuando el picking esté validado, pulse **Sincronizar con costo en
   destino**. El módulo:
   - Busca un `stock.landed.cost` en **borrador** que ya incluya este
     picking; si existe, lo reutiliza.
   - Si no existe, crea uno nuevo con este picking y las líneas
     capturadas.
   - Cada línea sincronizada nace con `expense_scope = 'picking'` y
     `picking_id = este picking`.
   - El vínculo entre la fila de gasto y la línea del LC se guarda en
     `landed_cost_line_id` (visible como columna opcional en la lista).

Al terminar, en la cabecera del picking aparece el stat button **Costos
destino** que abre el LC creado.

### 4.4. Sumar los gastos globales de la importación

Los gastos que aplican a ambas recepciones (flete internacional, seguro,
comisión bancaria, agente aduanal) se agregan de la forma habitual desde
`invoice_in_landed_cost`:

1. Abra el `stock.landed.cost` de la importación.
2. En la pestaña **Facturas de gastos** vincule las facturas de
   proveedor pertinentes. Sus líneas se copian automáticamente a
   **Costos adicionales**.
3. Cada línea copiada nace con `expense_scope = 'global'`. Puede
   cambiarlo manualmente si un renglón específico corresponde a un solo
   picking.

Si un gasto general fuera realmente exclusivo de una recepción (por
ejemplo, una guía aérea que solo cubrió la Recepción 2), edite el LC y
en la columna **Alcance** de la línea seleccione **Solo esta recepción**
+ el picking correcto en la columna **Recepción**.

### 4.5. Calcular y validar el costo en destino

1. En el LC, pulse **Calcular**. El módulo aplica el reparto:
   - Cada línea **global** se prorratea entre **todos los movimientos**
     de los pickings del LC.
   - Cada línea **por picking** se prorratea entre los **movimientos de
     su picking**.
   - Ambos ajustes se **suman** producto por producto en la pestaña
     _Ajustes de valoración_ y en el resumen _Costos por Producto_.
2. Revise la vista previa (columnas: cantidad, valor anterior, costo
   adicional, nuevo valor).
3. Pulse **Validar / Registrar**. Odoo registra el ajuste contable y
   actualiza el standard price de los productos valuados en tiempo real.

Si algo quedó mal repartido, use `cancel_landed_cost_odoo` para
revertirlo y volver a calcular. Este módulo no interfiere con la
cancelación.

---

## 5. Ejemplo numérico

| Concepto | Recepción 1 | Recepción 2 |
|---|---|---|
| Producto | Reactivo A × 80 uds | Equipo B × 20 uds |
| Costo base (compra) | USD 8 000 | USD 12 000 |
| Permisos de importación | USD 100 | USD 250 |
| Derechos arancelarios | USD 800 | USD 1 200 |
| Flete internacional (global) | — (se prorratea) | — (se prorratea) |
| Seguro (global) | — (se prorratea) | — (se prorratea) |

Con **Flete global = USD 2 000** y **Seguro global = USD 400** (método
por cantidad; total 100 unidades):

| Producto | Costo base | Global (24/ud) | Picking (12,5/ud R1; 72,5/ud R2) | Total unitario |
|---|---|---|---|---|
| Reactivo A (80 uds) | 100 | 24 | 12,5 | 136,5 |
| Equipo B (20 uds) | 600 | 24 | 72,5 | 696,5 |

Notas del cálculo:

- **Global**: (2000 + 400) / 100 uds = 24 por unidad.
- **Picking R1**: (100 + 800) / 80 uds = 12,5 por unidad, aplicado solo
  a Reactivo A.
- **Picking R2**: (250 + 1200) / 20 uds = 72,5 por unidad, aplicado solo
  a Equipo B.

Los tres bloques se suman al costo base y se guardan en
`valuation_adjustment_lines`. El resumen del reporte PDF muestra las
columnas **Alcance** y **Recepción** para trazar de dónde viene cada
importe.

---

## 6. Reporte PDF

El reporte oficial de `invoice_in_landed_cost` (**Imprimir → Costo en
destino**) incorpora dos nuevas columnas en la tabla _Costos
adicionales_:

- **Alcance** — _Toda la importación_ / _Solo esta recepción_.
- **Recepción** — nombre del picking (solo para líneas con alcance
  picking).

El resto del reporte (Costos por Producto, Ajustes de valoración) no
requiere cambios: los totales ya reflejan el reparto por picking porque
las adjustment lines se generan correctamente.

---

## 7. Preguntas frecuentes

**¿Puedo dividir en más de dos recepciones?**
Sí. Confirme la primera división, luego lance el wizard nuevamente sobre
el _Picking 1_ resultante (que sigue en borrador) para dividirlo otra
vez. El módulo etiqueta ambas mitades como _first_/_second_ para
trazabilidad, pero no hay tope funcional.

**¿Qué pasa si aparece un backorder automático?**
El backorder estándar de Odoo (cuando validas parcialmente un picking)
sigue funcionando. Ese picking hijo heredará las flags del padre pero
no las líneas de gasto: agréguelas manualmente si aplica.

**¿Puedo capturar un gasto por picking en un LC que ya tenga líneas
globales?**
Sí. En el `stock.landed.cost`, agregue una fila en _Costos adicionales_,
elija **Alcance = Solo esta recepción** y seleccione el **Recepción**
correcto (el dominio se limita a los pickings del LC).

**¿Qué pasa si un gasto viene en factura pero solo aplica a un
picking?**
Vincule la factura al LC como siempre. Odoo copia las líneas con alcance
_Toda la importación_ por defecto; edítelas en la lista y cambie el
alcance + el picking. Al calcular se reparten solo en ese picking.

**¿Cómo verifico que el reparto por picking se activó?**
Al **Calcular** el LC:

- Todas las líneas de valoración de la línea global tienen movimientos
  de _ambos_ pickings.
- Las líneas de valoración de la línea con scope picking solo tienen
  movimientos del picking indicado.

Si no ve esa separación, revise que la línea tenga _expense_scope =
picking_ y _picking_id_ dentro de los pickings del LC.

**El monto de una línea sincronizada aparece en cero.**
Ocurre si intentó crear la línea directamente en el LC sin
`invoice_amount_lc`. La lógica USD/tasa de `invoice_in_landed_cost`
recalcula `price_unit` a partir de `invoice_amount_lc` y lo pone en cero
si está vacío. El módulo ya cubre este caso al sincronizar desde el
picking (replica `amount` en `invoice_amount_lc`). Si edita el LC a
mano, capture ambos campos con el mismo importe.

---

## 8. Solución de problemas

| Síntoma | Posible causa | Acción |
|---|---|---|
| Botón _Dividir recepción_ no aparece | OC sin _Compra internacional_ o sin picking en borrador | Marcar el flag y confirmar la OC nuevamente. |
| Wizard se queda en rojo en columna _Diferencia_ | La suma de Recepción 1 + Recepción 2 no coincide con la original | Ajustar cantidades. |
| _Sincronizar con costo en destino_ da error _Registre al menos una línea de gasto_ | La pestaña de gastos está vacía | Capturar al menos una fila antes de sincronizar. |
| Se creó un LC nuevo cuando ya había uno | El LC previo estaba validado, no borrador | Cancele el LC anterior o edite manualmente para consolidar. |
| Al calcular, el costo global no se ve | Los productos usan valuación _estándar_ | Ajuste la categoría a FIFO / Precio promedio. |
| Al validar, no se genera asiento contable | Categoría en valuación _periódica_ | Ajuste a _real_time_ o registre el asiento manualmente. |

---

## 9. Modelos y campos técnicos

Para desarrolladores o consultores que necesiten personalizar el flujo:

- `stock.landed.cost.lines`
  - `expense_scope` (selection: `global`/`picking`)
  - `picking_id` (Many2one a `stock.picking`)
  - Constraint: si `expense_scope='picking'`, `picking_id` es
    obligatorio y debe estar dentro de `cost_id.picking_ids`.
- `stock.landed.cost`
  - Override de `compute_landed_cost` que sólo se activa si alguna
    línea tiene `expense_scope='picking'`.
  - Método público `_get_moves_for_cost_line(cost_line)` que devuelve
    el recordset de movimientos elegibles según el alcance.
- `stock.picking`
  - `gn_import_reception_split` (Boolean)
  - `gn_import_reception_part` (Selection `first`/`second`)
  - `gn_import_extra_cost_line_ids` (One2many a
    `gn.import.extra.cost.line`)
  - `gn_import_landed_cost_ids` (Many2many computed, LC vinculados)
  - `action_gn_import_sync_landed_cost()` — botón de sincronización.
- `gn.import.extra.cost.line` (nuevo)
  - `picking_id`, `expense_type`, `product_id`, `name`, `amount`,
    `currency_id` (related), `split_method`, `vendor_bill_id`,
    `landed_cost_line_id` (referencia).
  - Método `_prepare_cost_line_vals(cost)` — replica los datos como
    diccionario listo para `create/write` de `stock.landed.cost.lines`
    (incluye `invoice_amount_lc = amount`).
- `purchase.order`
  - Campo computado `gn_import_split_available`.
  - `action_gn_import_split_reception()` — abre el wizard.
- `purchase.split.reception.wizard` (transient) con líneas
  `purchase.split.reception.wizard.line`.

---

## 10. Historial de versiones

| Versión | Fecha | Cambios |
|---|---|---|
| 19.0.1.0.0 | 2026-07-09 | Versión inicial: wizard de división, gastos por picking, reparto híbrido, extensión al reporte PDF. |
