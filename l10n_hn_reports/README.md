# l10n_hn_reports

Reportes fiscales Honduras (SAR / Formulario 904), libros de compras y ventas, y asistente de **cierre ISV en borrador**.

## Entorno (Odoo Community + LABHOSPY)

Mismo `addons-path` y `--data-dir` en servidor, actualizaciones y pruebas:

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy-test \
  -d LABHOSPY-TEST -p 5025
```

Actualizar solo este módulo:

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy-test \
  -d LABHOSPY-TEST -u l10n_hn_reports --stop-after-init
```

Perfil recomendado: **`l10n_hn_pyme`** (ordena dependencias: plan HN, 904, libros, retenciones, DMC, tasas BCH).

## Checklist mensual (operativo)

1. **904 (ISV)** — Contabilidad → Informes → **Honduras (SAR / fiscal)** → asistente 904: revisar casillas y totales vs. mayor / criterios SAR.
2. **Libro de compras / ventas** — mismo menú: exportar XLSX y cruzar con facturas del período.
3. **DMC** — módulo `l10n_hn_dmc` (compras, CAI, exclusiones): exportar para el mismo mes y comparar con libro/904.
4. **Retenciones** — módulo `l10n_hn_retentions`: comprobantes y, si aplica, **Resumen retenciones (XLSX)** bajo Contabilidad → Informes (pagos publicados con líneas de diferencia / retención).
5. **Cierre ISV (borrador)** — asistente **Cierre ISV (borrador)**: configurar en la compañía diario y cuentas por defecto; genera un asiento tipo **borrador** según casillas 21 y 31 del mismo informe. Validar períodos / ejercicio fiscal si `l10n_hn_account` exige cerrados.

### Prueba manual recomendada (mismo período)

1. Registrar facturas de compra con impuestos ya etiquetados 904.
2. Exportar **Libro de compras** y **DMC** para el mismo mes.
3. Comparar bases, ISV y totales con el mayor y con el 904.

## Form 904 (ISV)

- Etiquetas en `data/sar_tax_tags_data.xml` (`casilla_904` en `account.account.tag`).
- Tras instalar o actualizar el módulo, se ejecuta la sincronización que **asigna esas etiquetas** al reparto de los impuestos estándar del plan HN (ISV 15 %, exento, exonerado venta, etc.). Revisar en Contabilidad → Configuración → Impuestos si el nombre de un impuesto personalizado no coincide con la regla heurística.
- Los totales del asistente 904 usan líneas con `tax_tag_ids` en el período. **Validar siempre contra los criterios SAR** antes de declarar.

## Libros y DMC

- **Libro compras/ventas**: transitorio `hn.libro.report` (XLSX).
- **DMC** (`l10n_hn_dmc`): usa `l10n_hn_account` (`cai_invoice`, `excluir_compra`, importes 15 %/18 %, etc.).

## Cierre ISV (borrador)

- Campos en **Configuración → Ajustes → [compañía]** (pestaña relacionada con reportes HN / ISV): diario y cuentas débito/haber por defecto.
- El asistente propone importe coherente con casillas **21 − 31** del 904; si el importe es negativo, invierte débito y haber.
- El asiento queda en **borrador** para revisión contable antes de publicar.

## Fases siguientes (fuera de este módulo, roadmap CE)

- **Presupuesto:** analytic / `account_budget` en CE o módulos de terceros según el proyecto.
- **Caja:** diarios banco y efectivo, extractos y conciliación; caja registradora solo si el negocio lo pide.
- **Márgenes:** coste en producto o movimientos e informes de margen por pedido o exportación a BI.

Estas líneas son orientativas; la implementación concreta depende de módulos adicionales acordados para LABHOSPY.

## Obsoleto

- **`nahuiik_report`**: sustituido por `l10n_hn_account` (libros PDF/XLS clásicos y wizard ISV), por este módulo más `l10n_hn_dmc`; el addon `nahuiik_report` queda como stub deprecado (`installable: False`).

## Multi-moneda

Los libros y el 904 van en **HNL** según normativa; el detalle opcional en facturas USD usa columnas informativas donde aplica.
