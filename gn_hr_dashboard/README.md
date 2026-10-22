# GN HR Dashboard

Dashboard de RRHH para Odoo 19: informes de empleados y vista regional multi‑compañía.

## Desarrollador

- **Grupo Nahuiik** — [www.gruponahuiik.com](https://www.gruponahuiik.com) — [info@gruponahuiik.com](mailto:info@gruponahuiik.com)

## Dependencias declaradas

`mail`, `hr`, `web`, `hr_payroll`, `hr_holidays`

## Opcionales (funciones extra si están instalados)

- `gn_hr_intercompany` — grupo de gestor regional
- Modelo `gn.hn.hr.attendance.incident` — KPIs de incidencias / horas extra
- `l10n_hn_hr_payroll` — wizard completo de informes desde la pestaña Informes

## Extender informes

Registrar categorías en el registry OWL `employee_report_categories` desde un JS cargado en `web.assets_backend` después de los assets de este módulo. Ver comentarios en `static/src/employee_report_registry.js`.

## Actualizar módulo

```bash
python3 odoo-bin ... -d BASE -u gn_hr_dashboard --stop-after-init
```

## Licencia

LGPL-3 (ver manifest).
