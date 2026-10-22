# Convivencia: `gn_qif_openai_reconcile` ↔ `gn_account_reconcile_ce`

Este documento existe para que **nadie interprete como lo mismo**:

- Importar/analizar extractos (este módulo), y  
- Emparejar banco contra **apuntes contables ya existentes** (módulo `gn_account_reconcile_ce`).

## Tabla de decisión rápida

| Objetivo | Módulo / pantalla típica |
|----------|--------------------------|
| Importar **QIF, XLS, XLSX, PDF** u operar IA sobre archivos · lotes carpeta · layouts banco | **gn_qif_openai_reconcile** (asistentes, historial, etc.) |
| Tras import, lista OWL líneas extracto (+ banner import) · atajos | **Este módulo** · vista lista `gn_qif_bank_st_line` |
| Ver **presets reconciliación** Odoo CE (`account.reconcile.model`): candidatos IA y plantillas con cuentas | **Este módulo** · botón **«Candidatos»**, menú «Modelos CE», wizard **Plantillas modelo conciliación** |
| Persistir texto↔cuenta antes de modelo · **Learn** IA | **`gn.qif.reconcile.learn`** (solo Nahuiik) |
| **Empareljar línea extracto contra `account.move.line`** (factura abierta, pago, cuenta conciliable) con ranking monto/contacto/fecha/ref | **`gn_account_reconcile_ce`** · Workspace cliente «matching inteligente» |

## Qué *no* hace cada uno (para no esperar fantasía del otro)

| Expectativa incorrecta | Realidad |
|------------------------|----------|
| «**Candidatos** en lista Nahuiik me dan facturas AML» | Ahí se enlaza a **`account.reconcile.model`** ordenados por diario/reglas/learn — **no** es el mismo buscador AML que CE matching. |
| «El workspace CE crea presets por etiqueta como la IA Nahuiik» | El workspace **solo** clasifica AML y ejecuta reconcile; crear preset va por **wizard plantillas** o IA → modelo CE en Nahuiik. |
| «Un solo clic siempre reconcilia multimoneda/partials bien» | Puede fallar; revisar límites documentados en el PLAN del módulo CE. |

## Orden recomendado de trabajo

1. Import (Nahuiik) → líneas en diario.  
2. Si hace falta **reglas repetibles** → plantillas Nahuiik o promoción IA a `account.reconcile.model`.  
3. Si hace falta **empatar con algo ya contabilizado** → abrir **`gn_account_reconcile_ce`** con el mismo diario (`default_journal_id` si enlazáis tras import).

## Licencias en el mismo proyecto

Este addon es **OPL-1**; `gn_account_reconcile_ce` se declara **LGPL-3**. Acoplar con `depends` o redistribuir junto debe alinearse con vuestra política comercial antes de producir instaladores únicos.
