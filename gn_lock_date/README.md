# GN Lock Date

## Objetivo

Este módulo combina:

1. **Bloqueo granular por diario y rango de fechas** (`gn.period.lock`): impide crear, modificar o publicar asientos en fechas bloqueadas para los diarios indicados.

2. **Paridad funcional con el flujo de “Lock Dates” de Odoo CE 19**: usa los campos nativos de `res.company` (global, impuestos, ventas, compras, hard lock) y el modelo `account.lock_exception`, sin código Enterprise.

3. **Interfaz OWL**: dashboard “Lock Dates”, asistente de fechas con validaciones suaves en el cliente, y aviso opcional en el formulario de `account.move` cuando aplica un bloqueo granular `gn.period.lock`.

## Menús

- **Contabilidad (app) → Contabilidad → Bloqueando** (“Closing” en inglés): **Fechas de bloqueo...** — modal OWL (`Bloquear asientos contables`) que escribe los campos nativos de `res.company`.
- **Contabilidad → Configuración → Lock Dates**: dashboard, bloqueos por diario (`gn.period.lock`) y excepciones (`account.lock_exception`).

El formulario de period lock incluye el botón **Lock Dates Center** (dashboard) para usuarios asesores.

## Dependencias técnicas

- `account`, `mail`, `web`

## Grupos de seguridad

- **Usuario / desbloqueo / administrador GN** (sin cambios conceptuales).
- **Administrador de bloqueo de período** ahora **implica** `account.group_account_manager` para alinear el rol “admin GN lock” con el asesor contable estándar de Odoo.

## Assets (Odoo 19 CE)

Registrados en `web.assets_backend`:

- `static/src/lock_journal_entries_modal/*` — acción cliente `gn_lock_date.lock_journal_entries` (modal nativo `target="new"`, pie Guardar/Descartar)
- `static/src/lock_dates_wizard/*` — vista formulario `lock_dates_wizard_form` en el asistente
- `static/src/account_move_lock_warning/*` — parche de `FormController` para avisos no bloqueantes

## Instalación y actualización

1. Coloca el módulo en el `addons-path`.
2. Actualiza la lista de aplicaciones e instala o actualiza **GN Lock Date**.

Ejemplo:

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d TU_BASE_DE_DATOS \
  -u gn_lock_date \
  --stop-after-init
```

## Soporte

Grupo Nahuiik — https://www.gruponahuiik.com

## Licencia

LGPL-3
