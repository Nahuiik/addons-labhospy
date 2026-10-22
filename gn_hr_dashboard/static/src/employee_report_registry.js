/** @odoo-module **/

/**
 * API única para el tab "Informes de empleados" del dashboard RRHH (`gn_hr_main_dashboard`).
 *
 * Los módulos de localización o extensión deben importar `employeeReportCategoriesRegistry`
 * desde este archivo y llamar a `.add(id, { id, label, icon, color, sequence, reports }, opts)`.
 * No duplicar componentes OWL ni acciones cliente: el shell vive en gn_hr_dashboard.
 *
 * Extensiones: en el manifest del addon, declare un JS en web.assets_backend **después** de los assets
 * de gn_hr_dashboard e importe este módulo con la ruta que resuelva el bundler del proyecto (suele ser la
 * ruta de archivo relativa al addon o la convención que usen sus otros imports ES6).
 */

import { registry } from "@web/core/registry";

export const employeeReportCategoriesRegistry = registry.category(
    "employee_report_categories"
);
