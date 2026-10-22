/** @odoo-module */

import { Component, useState, onWillStart, onWillUpdateProps, onPatched, onMounted } from "@odoo/owl";
import { formatDate, parseDate } from "@web/core/l10n/dates";
import { formatFloat } from "@web/views/fields/formatters";
import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";
import { useService } from "@web/core/utils/hooks";
const SERVER_DATE_FORMAT = "yyyy-MM-dd";


export class LocationsContainer extends Component {
    static template = "product.stock.balance.locationsHierarchyWidgetContainer";
    static props = {
        locations: { type: Array },
        productContext: { type: Object },
    };
    /*
    * The method to set up initial values
    */
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.psbTable = null;
        this.state = useState({
            locationsElements: null,
            dateStart: null,
            dateEnd: null,
            qty_available: 0,
            qty_available_total: 0,
        });
        const getPickerProps = () => {
            const value = [this.dateStartLocal, this.dateEndLocal];
            const pickerProps = { value, type: "date", range: true };
            return pickerProps;
        };
        this.dateTimePicker = useDateTimePicker({
            target: "rootStart",
            get pickerProps() {
                return getPickerProps();
            },
            onApply: (value) => {
                this._onDatesChange(value);
            },
        });
        onWillStart(async () => {
            await this.onRenderLocations(this.props);
            const PSBsettings = await this.orm.call("stock.location", "action_get_settings", []);
            Object.assign(this, {
                maxLevel: PSBsettings.max_level,
                showDates: PSBsettings.show_dates,
                allowExport: PSBsettings.allow_export,
                showTotal: PSBsettings.show_total,
                colNum: PSBsettings.columns,
            });
            await this.onGetTotal(this.props);
            this.decimalPrecision = await this.orm.call("stock.location", "action_get_decimal_precision", []);
        });
        onWillUpdateProps(async (nextProps) => {
            const proms = [
                this.onRenderLocations(nextProps),
                this.onGetTotal(nextProps),
            ];
            return Promise.all(proms);
        });
        onMounted(async () => {
            this.psbTable = this.el;
            this._hideToManyLevels();
        });
        onPatched(async() => {
            this._hideToManyLevels();
        });
    }
    /*
    * Getter for the dateStartLocal to parse the dateStart in the correct locale
    */
    get dateStartLocal() {
        return this.state.dateStart ? parseDate(this.state.dateStart) : false;
    }
    /*
    * Getter for the dateEndLocal to parse the dateEnd in the correct locale
    */
    get dateEndLocal() {
        return this.state.dateEnd ? parseDate(this.state.dateEnd) : false;
    }
    /*
    * The method to get locations and rerender the component
    */
    async onRenderLocations(props) {
        var locationsElements = await this.orm.call(
            "stock.location",
            "action_prepare_elements_for_hierarchy",
            [props.locations],
            { context: this.getLocalCtx(props) },
        );
        if (locationsElements.length == 0) { locationsElements = null };
        Object.assign(this.state, { locationsElements: locationsElements});
    }
    /*
    * The method to get totals
    */
    async onGetTotal(props) {
        if (this.showTotal) {
            const resSettings = this.getProductSettings(props);
            const product = await this.orm.call(
                resSettings.resModel,
                "read",
                [[resSettings.resId], ["qty_available", "qty_available_total"]],
                { context: this.getLocalCtx(props) },
            );
            Object.assign(this.state, {
                qty_available: product[0].qty_available,
                qty_available_total: product[0].qty_available_total
            });
        }
    }
    /*
    * The method to export the table
    */
    async _onExport(props) {
        const resSettings = this.getProductSettings(props);
        const action = await this.orm.call(
            resSettings.resModel,
            resSettings.resMethod,
            [[resSettings.resId]],
            { context: this.getLocalCtx(props) },
        );
        this.actionService.doAction(action);
    }
    /*
    * The method to add dates to context
    */
    getLocalCtx(props) {
        const localCtx = Object.assign({}, props.productContext, {
            from_date: this.state.dateStart || false,
            to_date: this.state.dateEnd || false,
        });
        return localCtx
    }
    /*
    * The method to get product settings
    */
    getProductSettings(props) {
        const resModel = props.productContext.template_id ? "product.template" : "product.product";
        const resId = props.productContext.template_id || props.productContext.product_id;
        const resMethod = props.productContext.template_id ? "action_prepare_xlsx_balance" : "action_prepare_xlsx_balance_product";
        return {
            resModel: resModel,
            resId: resId,
            resMethod: resMethod,
        };
    }
    /*
    * The method to process the period start change
    */
    async _onDatesChange(date) {
        Object.assign(this.state, {
            dateStart: date && date[0] ? formatDate(date[0], { format: SERVER_DATE_FORMAT }) : false,
            dateEnd: date && date[1] ? formatDate(date[1], { format: SERVER_DATE_FORMAT }) : false,
        });
        await this.onRenderLocations(this.props);
    }
    /*
    * The method to properply format stock figures
    */
    qtyFormatFloat(value) {
        if (!value) { return 0 };
        return formatFloat(value, { humanReadable: true, decimals: this.decimalPrecision })
    }

    /*
    * The method to hide/show levels based on level user clicks
    *  - In case we hide, we should hide also ALL children
    *  - In case we expand we should expand ONLY THE FIRST level
    */
    _onclickHide(event) {
        const icon = event.currentTarget;
        const row = icon.closest(".tr_location_class");
        if (!row) {
            return;
        }
        const currentLocationID = row.getAttribute("data-id");
        if (!currentLocationID) {
            return;
        }
        if (icon.classList.contains("fa-chevron-up")) {
            this._hideRecursive(currentLocationID);
        } else {
            this._expandFirstLevel(currentLocationID);
        }
    }
    /*
    * The method to hide elements recursively
    */
    _hideRecursive(currentLocationID) {
        const currentRow = this._getRowById(currentLocationID);
        this._setIconState(currentRow, "down");
        const childRows = this._getRowsByAttr("location", currentLocationID);
        childRows.forEach((row) => {
            row.classList.add("psb_hidden");
            this._setIconState(row, "down");
            const childId = row.getAttribute("data-id");
            if (childId) {
                this._hideRecursive(childId);
            }
        });
    }
    /*
    * The method to exapnd the very first hierarchy level
    */
    _expandFirstLevel(currentLocationID) {
        const currentRow = this._getRowById(currentLocationID);
        this._setIconState(currentRow, "up");
        const childRows = this._getRowsByAttr("location", currentLocationID);
        childRows.forEach((row) => {
            row.classList.remove("psb_hidden");
        });
    }
    /*
    * The method to hide levels through the initial rendering based on max level
    */
    _hideToManyLevels() {
        if (!this.psbTable || this.maxLevel === undefined || this.maxLevel === null) {
            return;
        }
        this._getRowsByAttr("level", this.maxLevel).forEach((row) => {
            const rowId = row.getAttribute("data-id");
            if (rowId) {
                this._hideRecursive(rowId);
            }
        });
    }
    /*
    * The method to expand all levels
    */
    _onclickExpandAll() {
        this._getAllRows().forEach((row) => {
            const rowId = row.getAttribute("data-id");
            if (rowId) {
                this._expandFirstLevel(rowId);
            }
        });
    }

    _getAllRows() {
        if (!this.psbTable) {
            return [];
        }
        return Array.from(this.psbTable.querySelectorAll(".tr_location_class"));
    }

    _getRowsByAttr(attr, value) {
        const stringValue = String(value);
        return this._getAllRows().filter((row) => row.getAttribute(attr) === stringValue);
    }

    _getRowById(rowId) {
        const stringId = String(rowId);
        return this._getAllRows().find((row) => row.getAttribute("data-id") === stringId) || null;
    }

    _setIconState(row, state) {
        if (!row) {
            return;
        }
        const icon = row.querySelector(".o_hide");
        if (!icon) {
            return;
        }
        const isUp = state === "up";
        icon.classList.toggle("fa-chevron-up", isUp);
        icon.classList.toggle("fa-chevron-down", !isUp);
    }
}
