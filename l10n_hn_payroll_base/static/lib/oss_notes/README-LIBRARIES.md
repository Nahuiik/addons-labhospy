# Librerías de línea temporal / Gantt (OSS y otras)

Archivos **vendados** en este módulo (sólo los de licencia clara para redistribución en un addon LGPL):

| Librería        | Archivos vendados                    | Licencia observada      | Notas |
|----------------|---------------------------------------|-------------------------|--------|
| **frappe-gantt** | `static/lib/frappe-gantt/*`         | MIT                     | Gráfico Gantt ligero; API por tareas con `start` / `end` en fecha. |
| **vis-timeline** | `static/lib/vis-timeline/*`         | Apache-2.0 / MIT (visjs) | Timeline con `groups` + `items`; ~560 KB minificado. |

## No vendadas aquí (revisar licencia antes de integrar)

| Librería           | Motivo típico |
|--------------------|---------------|
| **dhtmlxGantt**    | Modelo dual: uso comercial suele requerir licencia de pago; hay edición GPL con obligaciones de cumplimiento estrictas. No incluida. |
| **FullCalendar**   | El núcleo es OS; la vista **Resource Timeline** / **Scheduler** suele depender de complementos con licencia comercial. No incluida. |

Cada actualización mayor del addon debe **revisar** las licencias upstream si se cambia de versión de `frappe-gantt` o `vis-timeline`.
