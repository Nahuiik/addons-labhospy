# Error: `gn_creation_source` field is undefined (lista modelos reconciliación)

## Síntoma

En el navegador:

```text
Caused by: Error: "account.reconcile.model"."gn_creation_source" field is undefined.
```

Ocurre al abrir la **vista lista** (o formulario) de **Reconciliation models** cuando la **vista heredada** del módulo `gn_qif_openai_reconcile` ya incluye los campos `gn_creation_source` / `gn_file_format_key`, pero el **servidor no ha cargado** la extensión Python en `models/account_reconcile_model.py` (despliegue incompleto o módulo no actualizado).

## Solución correcta (recomendada)

1. Asegurarse de que en el servidor exista el archivo  
   `gn_qif_openai_reconcile/models/account_reconcile_model.py`  
   y que `models/__init__.py` contenga `from . import account_reconcile_model`.
2. Actualizar el módulo en la base de datos (misma instancia que sirve la URL):

```bash
python3 odoo-bin ... -d SU_BASE -u gn_qif_openai_reconcile --stop-after-init
```

3. Reiniciar el servicio Odoo y **forzar recarga** del frontend (Ctrl+F5 o limpiar caché).

Tras un `-u` correcto, la columna `gn_creation_source` debe existir en `account.reconcile.model` y el cliente deja de fallar.

## Alivio temporal (si no puede actualizar ya)

Desactivar la vista heredada que añade esos campos:

- Ajustes → Técnico → Interfaces de usuario → Vistas  
- Buscar: `account.reconcile.model.tree.gn.qif.openai` o modelo `account.reconcile.model` + nombre con `gn qif openai`  
- Desmarcar **Activo** en las herencias de `gn_qif_openai_reconcile` sobre `account.reconcile.model`, **solo** hasta aplicar la actualización.

No es definitivo: se pierden las columnas/extras Nahuiik en esa vista.

## Diagnóstico en log

El `post_init_hook` del addon **solo se ejecuta en la primera instalación** del módulo (Odoo 19). En cada actualización (`-u`) no vuelve a correr; el fallo debe resolverse con despliegue completo del Python + `-u` como arriba.
