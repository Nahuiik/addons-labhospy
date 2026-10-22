# Plan ampliado: `gn_account_reconcile_ce`

## Cómo no confundir este módulo con `gn_qif_openai_reconcile`

Dos cosas distintas viven sobre las mismas **líneas de extracto bancario**. Si se mezcla el propósito, el usuario espera “un solo botón mágico” y no encuentra lo que busca.

| Pregunta | Si la respuesta es **sí**… | Ir a… |
|---------|----------------------------|--------|
| ¿Quiero **aplicar un preset contable estándar** (regla por texto, cuenta de contrapartida, modelo Odoo CE) después de IA o manualmente? | **Modelos reconciliación** `account.reconcile.model` · plantillas Nahuiik | `gn_qif_openai_reconcile`: botones «Candidatos» / «Plantillas», menús de patrones IA, wizard plantillas |
| ¿Quiero **emparejar esta línea de banco con un apunte ya existente** (factura, pago abierto, otra cuenta conciliable) por similitud monto/contacto/fecha/ref? | Matching **statement line ↔ `account.move.line`** | **`gn_account_reconcile_ce`**: Workspace «matching inteligente» |
| ¿Solo necesito **importar** archivo banco/analizar con IA sin decidir conciliación aquí? | Flujo principal import | Solo `gn_qif_openai_reconcile` |

**Orden mental útil:**

1. **Importar / etiquetar** (Nahuiik QIF OpenAI): líneas llegan al diario con `payment_ref`, etc.
2. **Opcional crear reglas rápidas** (Nahuiik): modelo CE + patrones IA = “la próxima vez Odoo/Nahuiik sabe contra qué cuenta apuntar al validar modelo”.
3. **Emparejar con movimientos ya contabilizados** (este módulo): buscar AML candidato y ejecutar reconciliación contable típica CE (liquidez/suspense + contraparte).

**No están duplicados:** uno sugiere **presets de asiento**, el otro sugiere **pares contables pendientes**.

### Límites técnicos (ambos mundos)

- **Multimoneda** y reconciliaciones **parciales** o extractos con más de una contraparte: pueden necesitar trabajo manual en asiento nativo Odoo — no garantizar resultado automático desde el cliente.
- **Zero-click**: solo debe usarse donde el mejor score y los residuales se hayan revisado políticamente; el umbral vive en ICP (`gn_account_reconcile_ce.auto_accept_score`).

### Licencia y distribución

- **`gn_account_reconcile_ce`** se declara **LGPL-3**; **`gn_qif_openai_reconcile`** **OPL-1**. Una dependencia oficial `depends` entre ambos debe evaluarse con la política de licencias que use tu distribución antes de cerrar bundles.

Para detalle específico del lado import/patrones, ver en el otro addon: [`doc/CONVIVENCIA_ACCOUNT_RECONCILE_CE.md`](../gn_qif_openai_reconcile/doc/CONVIVENCIA_ACCOUNT_RECONCILE_CE.md).

---

## Frontend (implementado aquí vs. siguiente fase)

| Elemento | Estado |
|----------|--------|
| **OWL reconciliation widget** | Acción cliente `GnCeReconcileWorkspace` (lista extracto + candidatos + shortcuts). |
| **State manager** | Objeto **`reactive` (OWL)** dentro del servicio `gn_account_reconcile_ce` (`service.state`). |
| **Reconciliation service** | `gn_account_reconcile_ce` (registry `services`): RPC, viewport, teclado. |
| **Virtual list** | **Viewport slicing** (`sliceStatementsViewport` + spacer rows). |
| **renderer OWL nativo** | Plantillas Owl (`gn_ce_reconcile_client_action.xml`). |

Integración opcional FullCalendar sólo donde aporte; multimoneda/mejor splits = fases posteriores.

## Librerías

- **rapidfuzz** (servidor). **python-Levenshtein**: opcional. **fullcalendar**: no cargado aquí por peso bundle.

## Matching pipeline (`GnCeMatchingScorer`)

Ponderaciones del `composite`: monto exacto, partner, similaridad referencia, etiqueta difusa, tolerancia residual, proximidad fechas.

## UX y parámetros ICP

Ver `gn_ce_default_params` y claves:

- `gn_account_reconcile_ce.amount_tolerance`
- `gn_account_reconcile_ce.date_window_days`
- `gn_account_reconcile_ce.candidate_search_cap`
- `gn_account_reconcile_ce.auto_accept_score`

## Enlaces con `gn_qif_openai_reconcile`

Context útil cliente: `default_journal_id`, `gn_ce_auto_zero`. Documentación uso cruzado: `gn_qif_openai_reconcile/doc/CONVIVENCIA_ACCOUNT_RECONCILE_CE.md`.
