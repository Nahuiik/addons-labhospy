# Tablero Financiero (`gn_financial_dashboard`)

Tablero visual (OWL + Chart.js) de indicadores financieros sobre la
contabilidad de Odoo. Es un módulo **companion** del módulo comercial
`bi_financial_reports_comm` (BrowseInfo): **no lo modifica**, calcula sus
propios indicadores directamente sobre `account.move.line` (la misma fuente de
datos que los reportes BI) y, cuando ese módulo está instalado, ofrece accesos
directos (drill-down) a sus reportes para ver el detalle.

## Qué muestra

- **Salud financiera**: score 0–100 con semáforo y alertas automáticas.
- **Rentabilidad**: tarjetas KPI (ingresos, utilidad bruta, gastos, utilidad
  neta, margen neto) con comparación contra el período anterior; evolución
  mensual ingresos/gastos/utilidad; cascada de resultados; composición de
  gastos.
- **Liquidez y balance**: flujo de caja dedicado en la pestaña Liquidez,
  saldo bancario, por cobrar/pagar, capital de trabajo, razón corriente y
  prueba ácida.
- **Cartera por antigüedad**: tramos configurables (15/30/45/60 días) para
  cuentas por cobrar y por pagar, con saldo histórico a la fecha de corte
  (alineado al reporte BI). Tablas de terceros ordenables y drill-down coherente.

## Fuente de datos

Todo se calcula sobre `account.move.line` agrupado por `account_type`
(`_read_group`), respetando:

- Compañía (incluye sucursales vía `child_of`).
- Rango de fechas (por defecto, año fiscal a la fecha).
- Diarios seleccionados.
- Estado de asientos: *solo asentado* o *todos (incl. borrador)*.
- Comparación: período anterior / mismo período del año anterior / sin
  comparación.

Las cifras de KPIs siguen las mismas agrupaciones por tipo de cuenta que el
`executive.summary.report` del módulo BI, para mantener coherencia.

## Permisos

- `account.group_account_readonly` y `account.group_account_manager` pueden
  abrir el tablero (menú **Contabilidad › Reportes › Tablero financiero**).

## Notas técnicas

- Modelo RPC: `gn.financial.dashboard` (AbstractModel, solo métodos `@api.model`).
- No hay acoplamiento de escritura con el módulo BI; el único punto de contacto
  es `open_bi_report`, que abre las acciones cliente del módulo BI si existen.
- Multimoneda: importes en moneda de la compañía (`balance` del apunte).

## Instalación / actualización (LABHOSPY)

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY -i gn_financial_dashboard --stop-after-init
```
