/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Icono de ayuda con tooltip contextual reutilizable.
 *
 * Pensado para usarse en cabeceras de gráficos y secciones donde queremos
 * explicar al usuario qué significa el panel, cómo se calcula la información
 * y qué cuentas/datos lo alimentan.
 *
 * Props:
 *  - title (string): título corto en negrita.
 *  - desc (string): breve descripción de qué es.
 *  - formula (string, opcional): cómo se calcula.
 *  - accounts (string, opcional): cuentas/datos que utiliza.
 *  - hint (string, opcional): cómo interpretarlo.
 */
export class InfoTip extends Component {
    static template = "gn_financial_dashboard.InfoTip";
    static props = {
        title: { type: String, optional: true },
        desc: { type: String, optional: true },
        formula: { type: String, optional: true },
        accounts: { type: String, optional: true },
        hint: { type: String, optional: true },
    };
}
