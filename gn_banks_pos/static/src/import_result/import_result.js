/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

// Field widget OWL: presenta el resumen estructurado (Json) de la importación
// BAC POS como tarjetas + chips. La lógica de importación vive en el servidor.
export class BacPosImportResult extends Component {
    static template = "gn_banks_pos.BacPosImportResult";
    static props = { ...standardFieldProps };

    get data() {
        return this.props.record.data[this.props.name] || {};
    }

    get fileCount() {
        return (this.data.files || []).length;
    }

    get modeLabel() {
        return this.data.mode === "batch" ? _t("Lote") : _t("Un archivo");
    }
}

export const bacPosImportResult = {
    component: BacPosImportResult,
    supportedTypes: ["json"],
};

registry.category("fields").add("gn_bac_pos_import_result", bacPosImportResult);
