# gn_banks_dashboard

Dashboard OWL de tesorería para **gn_banks** (Odoo 19).

## Instalación

1. Añadir el addon al `addons-path` (carpeta `labhospy`).
2. Actualizar lista de aplicaciones e instalar **Dashboard de Tesorería**.
3. Dependencias: `gn_banks`, `gts_branch_management`, `account`, `web`.

## Uso

Menú: **Banks → Dashboard** (usuarios con grupo débitos/créditos, cheques o importación POS).

### Funcionalidad

- **18 KPIs** con variación vs período anterior y drill-down a listas filtradas.
- **Flujo de caja** diario (entradas, salidas, acumulado).
- **Gráficos**: tipo de operación, banco, sucursal, cheques, POS, top partners.
- **Alertas** operativas y bloque de **riesgo**.
- **Insights** generados en backend.
- **Tablas resumen** por dimensión con porcentaje y enlace al detalle.
- **Filtros**: fechas, compañía, diarios bancarios y **origen del flujo**.

### Origen del flujo (Entradas / Salidas / Flujo neto)

El selector **Flow source** controla de dónde salen las entradas/salidas y la
serie de flujo de caja:

- **Tesorería (gn_banks)** *(por defecto)*: agrega los documentos `gn_banks`.
  - Entradas = créditos + depósitos (`total`) + **neto** de liquidaciones POS
    (la parte que realmente llega al banco, no el bruto).
  - Salidas = débitos + cheques emitidos.
  - Las **transferencias internas** (entre cuentas propias) se excluyen del
    flujo neto; siguen visibles como KPI informativo.
- **Mayor contable**: calcula entradas (débitos) y salidas (créditos) desde
  `account.move.line` sobre las cuentas de los diarios banco/caja
  (`parent_state=posted`). Refleja **todo** el movimiento bancario real
  (cobros, conciliación, asientos manuales) y **reconcilia con el Saldo
  disponible**.
  - *Nota:* las transferencias entre dos cuentas bancarias propias inflan
    ambos lados (entrada y salida) aunque el neto sea cero.

El **Saldo disponible** y los montos **conciliado / no conciliado** siempre se
toman del mayor contable (incluyen saldos iniciales), independientemente del
modo elegido.

### Multimoneda

Los importes en moneda distinta a la de la compañía se **convierten** a la
moneda de la compañía (KPIs de flujo, cheques, transferencias y serie de flujo
de caja). Los desgloses/tablas de detalle siguen agregando por `total` del
documento.

### Rendimiento

- La serie de flujo de caja usa **una consulta agrupada por día** por fuente
  (antes: bucle día a día con 2-3 consultas por día).
- `_compute_kpi_values` (período actual + anterior) se calcula **una vez** por
  petición y se reutiliza en KPIs, insights e indicadores.

### API backend

Modelo abstracto `gn.banks.dashboard.service`:

| Método | Descripción |
|--------|-------------|
| `get_filter_options` | Opciones de filtros |
| `get_dashboard_data` | Payload completo |
| `get_kpis` | Solo KPIs |
| `get_cashflow` | Serie de flujo |
| `get_alerts` | Alertas |
| `get_summary_tables` | Tablas |
| `get_insights` | Frases automáticas |
| `get_risk_block` | Riesgo operativo |
| `get_drilldown_action` | `ir.actions.act_window` |

### Seguridad

Respeta permisos de `gn_banks`: si el usuario no puede leer `debit.credit`, `bank.check` o `bank.transfer`, esas métricas no se calculan ni se exponen en drill-down.

### Traducciones (es_GT)

- Archivo: `i18n/es_GT.po` (terminología alineada con `gn_banks`).
- Cadenas UI en inglés en código (`_()` / `_t()`) para exportación estándar Odoo.
- Tras actualizar traducciones:

```bash
python3 /home/odoo/src/odoo/odoo-bin --addons-path=... i18n import -d LABHOSPY -l es_GT /home/odoo/src/labhospy/gn_banks_dashboard/i18n/es_GT.po
```

- Regenerar plantilla: `odoo-bin i18n export gn_banks_dashboard -d LABHOSPY -l pot`

### Prueba local

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY -u gn_banks_dashboard --stop-after-init
```

Luego abrir Odoo → Banks → Dashboard, aplicar filtros y hacer clic en un KPI para validar el drill-down.
