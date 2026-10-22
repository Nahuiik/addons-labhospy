/** @odoo-module */

import { Component } from "@odoo/owl";
import { LocationsContainer } from "@product_stock_balance/components/location_hierarchy_container/location_hierarchy_container";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";


export class Many2ManyLocations extends Component {
    static template = "product.stock.balance.locationsHierarchyWidget";
    static components = { LocationsContainer };
    static props = { ...standardFieldProps };
    /*
    * The method to prepare the records ids
    */
    get locations() {
        return this.props.record.data[this.props.name].records.map((record) => record.data.id);
    }
    /*
    * The method to apply proper field context to compute locations
    */
    get productContext() {
        const localCtx = {};
        const productKey = this.props.record.resModel == "product.template" ? "template_id" : "product_id";
        localCtx[productKey] = this.props.record.data.id;
        return localCtx;
    }
};

export const many2ManyLocations = {
    component: Many2ManyLocations,
    supportedTypes: ["many2many"],
    relatedFields: [ { name: "id", type: "integer" } ],
};

registry.category("fields").add("locationsHierarchyWidget", many2ManyLocations);
