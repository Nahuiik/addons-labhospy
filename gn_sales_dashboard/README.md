# Dashboard de Ventas Premium (`gn_sales_dashboard`)

Centro de mando comercial gerencial para Odoo 19 con datos reales, ECharts, drill-down, semántica de KPIs y analítica avanzada.

## Instalación

1. Añadir el módulo al addons-path.
2. Instalar **Dashboard de Ventas Premium**.
3. Asignar grupo *Dashboard de Ventas: Usuario*.
4. Menú: **Ventas → Command Center → Dashboard de Ventas**.

## Dependencias

`sale_management`, `account`, `crm`, `web`, `gts_branch_management`

Integración opcional con `commission.target` (`sales_commission_generic`) para metas.

## Idioma

Traducción **`es_GT`** en `i18n/es_GT.po`. Tras actualizar el módulo, activar idioma Guatemala en Odoo.

## Estructura del dashboard (pestaña Resumen)

1. **KPIs principales** (6–8): ventas netas, margen bruto, crecimiento, cumplimiento de meta, ticket promedio, clientes activos, pipeline abierto, pronóstico de cierre.
2. **Métricas secundarias**: facturación bruta, notas de crédito, pedidos, facturas, clientes nuevos, tasa de conversión, devoluciones, etc.
3. **Índice de desempeño comercial** con barras explicativas por componente.
4. **Meta vs real** con proyección, ritmo diario y pronóstico de cierre.
5. **Alertas comerciales** (modo compacto con conteos por severidad).
6. **Tendencia de ventas netas** (2/3) + **Insights automáticos** (1/3).
7. **Top 5** vendedores, productos y clientes.

Ancho del contenedor: ~92 % de la pantalla, máximo 1800 px, responsive.

## KPIs y semántica

Cada KPI incluye: `tier` (primary/secondary), `direction` (up/down), `has_data`, `is_configured`, `empty_reason`, `semantic_tone`.

| Interpretación | direction | Ejemplo |
|----------------|-----------|---------|
| Más es mejor | up | ventas, margen, clientes |
| Menos es mejor | down | notas de crédito, devoluciones |

Estados sin datos muestran mensajes neutrales (p. ej. *Meta no configurada*, *Sin costos disponibles*, *No hay datos comparativos*) en lugar de `$0.00` engañosos.

## Índice de desempeño comercial

Score 0–100 ponderado por factores configurables:

- Crecimiento de ventas, cumplimiento de meta, margen bruto, conversión CRM, diversificación de clientes, control de devoluciones, cobertura de pipeline, clientes recurrentes, tendencia del ticket.

Cada factor devuelve: `normalized_score`, `weight`, `weighted_score`, `status`, `description`, `metric` (drill-down). La suma de contribuciones coincide con el score general.

## Fuentes de datos

| Indicador | Fuente |
|-----------|--------|
| Ventas netas | Facturas publicadas − notas de crédito (sin impuestos) |
| Pedidos | `sale.order` en estado sale/done |
| Margen | Líneas de factura − costo × cantidad |
| Pipeline | Oportunidades CRM abiertas |
| Metas | `sales.dashboard.target` o `commission.target` |
| Pronóstico | Ritmo diario acumulado + tendencia reciente |

## Secciones del dashboard

- **Resumen**: jerarquía gerencial, insights, top 5
- **Vendedores / Productos / Clientes / Pipeline**
- **Análisis**: Waterfall, Pareto, RFM, cohortes
- **Forecast**: Escenarios conservador/esperado/optimista
- **Alertas**: Vista completa con filtros por severidad
- **Operaciones**: Tablas paginadas server-side

## Filtros

Barra compacta: período, comparación, fechas, sucursal, equipo, vendedor, diario. **Más filtros**: almacén, categoría, canal, estado pedido. Chips removibles tras aplicar.

## Configuración

- **Ventas → Configuración → Dashboard de Ventas Premium**
- **Command Center → Metas comerciales** (gerente)
- **Command Center → Configuración** (admin): pesos health score, umbrales

## Exportaciones

- CSV de KPIs (botón Exportar) — incluye filtros y período
- PDF ejecutivo — KPIs principales, índice, meta, tendencia, alertas
- PNG del gráfico hero (desde el propio gráfico ECharts)

## Permisos

| Grupo | Acceso |
|-------|--------|
| Usuario | Ver dashboard |
| Gerente | Metas comerciales + botón Configurar meta |
| Administrador | Configuración completa |

## API RPC (retrocompatible)

`get_filter_options`, `get_dashboard_init`, `get_dashboard_core`, `get_dashboard_widgets`, `get_dashboard_advanced`, `get_table_page`, `get_entity_drilldown`, `get_drilldown_action`, `export_kpis_csv`, `export_table_csv`, `get_executive_report_action`

## Decisiones técnicas (v19.0.4.0.0)

- Capa UI en `models/sales_dashboard_ui.py`: semántica KPI, insights determinísticos, top5 y pronóstico resumido sin duplicar consultas core.
- Frontend OWL: componentes `SalesGoalTrackerCard`, `SalesInsightsPanel`, `SalesTop5Panel`, `kpi_semantics.js`.
- Caché frontend invalidado al cambiar filtros; datos de pestaña conservados en sesión.
- ECharts embebido en assets (sin CDN).

## Pruebas

```bash
python3 odoo-bin -d REALEZA -u gn_sales_dashboard --test-tags gn_sales_dashboard --stop-after-init
```

Escenarios cubiertos: KPIs con semántica, crecimiento sin comparación, init enriquecido (insights/top5/health/goal), export CSV, drill-down, widgets y tablas.

## Nota

Coexiste con `gn_sales_report`. Este módulo usa tag OWL **`gn_sales_command_center`**.
