/** @odoo-module */

/**
 * Campo relacional para listas de ajustes en la ficha empleado.
 * Expone el nombre técnico histórico `salary_attachment_2many` reutilizando el motor
 * estándar de Odoo para X2many (sin copiar implementaciones de terceros).
 */

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { x2ManyField } from "@web/views/fields/x2many/x2many_field";

const salaryAttachmentMany2manyField = {
    ...x2ManyField,
    displayName: _t("Payroll adjustment lines"),
};

registry.category("fields").add("salary_attachment_2many", salaryAttachmentMany2manyField);
