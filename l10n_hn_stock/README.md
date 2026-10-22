# l10n_hn_stock

## Objetivo
Extender el flujo de ventas, inventario y facturación en Odoo 19 para cubrir requisitos de Honduras: guías de remisión, control granular de permisos, bloqueo de ventas bajo costo y ocultamiento selectivo de información sensible.

## Requisitos
El módulo depende de `sale_management`, `sale_margin`, `sale_stock_margin`, `stock_account` y `account`. Asegúrate de tenerlos instalados y disponibles en la ruta de addons.

## Características principales
- Generación de guías de remisión hondureñas con secuencias propias y reporte PDF listo para imprimir.
- Permisos específicos para confirmar ventas, editar precios en cotizaciones y facturas, o poder vender por debajo del costo.
- Validaciones automáticas en líneas de venta y factura que impiden colocar precios unitarios inferiores al costo salvo que el usuario posea el permiso especial.
- Campo `price_unit` en modo solo lectura para usuarios restringidos; el bloqueo aplica en formulario/listado y en onchange.
- Nuevo grupo `Ver costos y márgenes` que gobierna la visibilidad de costos (purchase_price, standard_price, avg_cost, total_value, etc.) y márgenes tanto en vistas como en reportes analíticos.
- Configuración corporativa para bloquear existencias negativas y controles por ubicación (permitir negativo y verificación de serie) directamente desde inventario.
- **Inventario / contabilidad (Honduras):** pestaña en la compañía para **diario de existencias** y **cuenta de valoración**; en categorías de producto el **diario de inventario** (valoración en tiempo real). Opción en **Ajustes → Inventario** (*Ajustes de inventario: fechas contables alineadas (HN)*): si está **activa**, se aplica la alineación de fechas contables/conteo/asiento y el reintento de asiento en ajustes; si está **desactivada**, el comportamiento es el estándar de Odoo.
- Registro y control de consumos internos mediante el modelo `consume.product`, con secuencias dedicadas, generación automática de movimientos y menú en Inventario.
- Menú adicional **Incoming Products** para altas internas, con flujo idéntico pero entren en modo entrada automática.
- El consumo interno genera asientos contables (journal configurable en el formulario) con enlace directo al comprobante resultante.
- Sincronización de datos clave entre ventas y documentos derivados (albaranes/facturas) según los flujos locales.

## Instalación
1. Copia el directorio `l10n_hn_stock` dentro de tu carpeta de addons (`/opt/odoo19/addons-odoo`).
2. Reinicia el servicio de Odoo para que cargue los nuevos módulos.
3. Ve a **Aplicaciones** > **Actualizar lista** y busca **l10n_hn_stock**.
4. Instala el módulo desde la interfaz o usando `-i l10n_hn_stock` en la línea de comandos.

## Configuración y uso
- Asigna los grupos según el nivel de acceso requerido:
  - `Confirmar venta` para poder confirmar órdenes.
  - `Editar precio venta` / `Editar precio factura cliente` para habilitar la edición de precios.
  - `Permitir vender debajo del costo` para omitir el bloqueo de precio contra costo.
  - `Ver costos y márgenes` para mostrar costos standard, purchase_price, márgenes y totales valorizados.
- En ventas y facturas, cualquier intento de ingresar un precio menor al costo disparará un aviso y restablecerá el valor si el usuario no tiene permiso.
- En albaranes activa la opción **Guía de remisión**, usa el botón **Generar guía de remisión** y luego imprime el reporte.
- Gestiona consumos internos desde **Inventario → Consume Products** creando movimientos internos (y de entrada si se marca *Incoming*) con seguimiento de pickings.

## Soporte
Para dudas o mejoras contacta a Grupo Nahuiik (https://www.gruponahuiik.com). Se aceptan PRs y reportes de issues específicos del localization pack.
