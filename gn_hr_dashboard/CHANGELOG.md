# Changelog

## 19.0.1.0.12 (2026-03-24)

- Vista regional: fila con gráficos (ausencias por tipo en barras horizontales, sexo, bandas de antigüedad); línea de costo nómina/empleado por mes; altas/bajas con eje dual y headcount fin de mes; línea y circular por tipo de contrato (si existe el campo).
- Backend: `payroll_per_employee_trend`, `contract_type_distribution`, `contract_type_monthly`, `headcount_end` en `movement_trend`, helper `_headcount_at_date`.
- Ayuda: textos para los nuevos gráficos y definiciones actualizadas.

## 19.0.1.0.11 (2026-03-24)

- Vista regional: costo de nómina por empleado; tabla de ausencias por tipo de permiso; gráfico de plantilla por sexo; bandas de antigüedad; bloque de reclutamiento (hr.job y, si aplica, hr.applicant); variación % de horas extra respecto al mes calendario anterior.
- Pestaña Ayuda: descripción de los indicadores anteriores.

## 19.0.1.0.10 (2026-03-24)

- Dashboard: `setDisplayName` con carácter de ancho cero en lugar de cadena vacía para no mostrar la etiqueta «Sin nombre» del breadcrumb.

## 19.0.1.0.9 (2026-03-24)

- Dashboard: orden de pestañas Vista regional → Informes → Ayuda; pestaña Ayuda con documentación de KPIs regionales.
- Informes: sin título duplicado en la barra; el cliente limpia el nombre de la acción en breadcrumb/título.
- Apertura por defecto: menú informes abre la pestaña Informes; menú regional abre Vista regional; sin clave en el contexto, pestaña inicial Informes.

## 19.0.1.0.8 (2026-03-24)

- Seguridad: grupo regional implica también `hr.group_hr_manager` para alinear permisos con KPIs que usan campos de contrato.
- Controlador: comprobación de `gn_hr_intercompany` instalado antes de evaluar su grupo; headcount con `read_group`; nómina del período con `read_group` y suma de `gross_wage`; antigüedad media con `search_read` (solo `contract_date_start`); eliminado código muerto `_payslips_overlapping`.
- Frontend: `hasGroupSafe` para xmlid de intercompany; pestañas principales con `_t`; wizard de informes con manejo amable si falta el módulo de localización.
- UX: etiqueta de alerta aclarando que cuenta actividades con resumen «Contrato por vencer».
- Documentación: `README.md`, `CHANGELOG.md`, `static/description/index.html`, icono en `static/description/icon.png`.
- Manifest: sitio web y contacto en autor.
