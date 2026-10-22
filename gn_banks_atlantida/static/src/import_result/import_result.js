/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

// Field widget OWL: presenta el resumen estructurado (Json) de la importación
// Atlántida POS como tarjetas + chips. La lógica de importación vive en el servidor.
export class AtlantidaPosImportResult extends Component {
    static template = "gn_banks_atlantida.AtlantidaPosImportResult";
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

export const atlantidaPosImportResult = {
    component: AtlantidaPosImportResult,
    supportedTypes: ["json"],
};

registry.category("fields").add("gn_atlantida_pos_import_result", atlantidaPosImportResult);
