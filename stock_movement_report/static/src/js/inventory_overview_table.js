/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Pager } from "@web/core/pager/pager";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { download } from "@web/core/network/download";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { DateTimeInput } from '@web/core/datetime/datetime_input';
import { WarningDialog } from "@web/core/errors/error_dialogs";
import { ConfirmationDialog, AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const { DateTime } = luxon;
import { Component, onWillStart, useState, useSubEnv, useRef, onMounted} from "@odoo/owl";

export class PrintConfirmationDialog extends ConfirmationDialog {
    static template = "stock_movement_report.PrintConfirmationDialog";
    static props = {
        ...ConfirmationDialog.props,
        body: String,
        printsingle: { type: Function, optional: true },
        printall: { type: Function, optional: true },
        printsingleLabel: { type: String, optional: true },
        printallLabel: { type: String, optional: true },
    };

    setup() {
        super.setup();
    }

    async _cancel() {
        return this.execButton(this.props.cancel);
    }

    async _printsingle_page() {
        return this.execButton(this.props.printsingle);
    }

    async _printall_page() {
        return this.execButton(this.props.printall);
    }
}

export class DeleteFavouriteRecord extends ConfirmationDialog {
    static template = "stock_movement_report.DeleteFavouriteRecord";
    static props = {
        ...ConfirmationDialog.props,
        resId: { type: Number },
    };

    setup() {
        super.setup();
        this.rpc = rpc;
        this.notification = useService("notification");
    }

    get i18n() {
        return {
            yes: _t("Yes"),
            no: _t("No"),
        };
    }

    displayNotification(text){
        this.notification.add(text, { type: "danger" });
    }

    async _confirmDelete() {
        var self = this;
        const resId = this.props.resId;
        self.rpc("/delete/fav_menu", {
            'res_id': resId,
        }).then(async function (result) {
            self.displayNotification(_t("Favorite record is deleted successfully!"))
        });
        window.location.reload();
        this.props.close();
    }

    async _cancelDelete() {
        this.props.close();
    }
}


export class StockMovementReportAction extends Component {
    static template = "stock_movement_report.InventoryReport";
    static props = { ...standardActionServiceProps };
    static components = {
        Pager,
        ControlPanel,
        Dropdown,
        DropdownItem,
        MultiRecordSelector,
        DateTimeInput
    };

    setup() {
        super.setup();
        var self = this;
        this.rpc = rpc;
        this.actionService = useService("action");
        this.ui = useState(useService("ui"));
        this.dialog = useService('dialog');
        this.orm = useService('orm');
        this.report_ref = useRef('report_body');
        this.report_model = 'inventory.movement.report';
        this.report_id = this.props.action.id;
        this.pagerState = { limit: 80, offset: 0 };
        this.notification = useService("notification");
        this.search_filters = this._buildSearchFilters();
        this.currentFavorites = false;
        this.context = useState(this.props.action.context);
        this.activeDropdown = null;
        this.debounceTimeout = null;

        const storedOptions = browser.sessionStorage.getItem('inventory_movement_report_options');
        if (storedOptions && Object.entries(JSON.parse(storedOptions)).length > 0) {
            this.search_filters = JSON.parse(storedOptions);
        }

        const storedPagerState = browser.sessionStorage.getItem('pagerState');
        if (storedPagerState && Object.entries(JSON.parse(storedPagerState)).length > 0) {
            this.pagerState = JSON.parse(storedPagerState);
        }

        this.currentFavorites = browser.sessionStorage.getItem('currentFavorites') || this.currentFavorites;


        onWillStart(async () => {
            const currentUserId = this.props.action.context.current_user_id;
            const user_companies = await this.orm.call('res.users', 'get_companies', [[['id', '=', currentUserId]]]);
            const allCompanies = await this.orm.call('res.company', 'search_read', [[], ['id', 'name', 'child_ids', 'parent_id']]);
            this.allCompanies = allCompanies;
            this.company_id = user_companies
            this.favouriteRecords = await this.rpc("/get/favorite/list", { 'model_name': this.report_model });
            const values = await this.orm.call('inventory.movement.report', 'get_html', [[this.report_id], this.search_filters, this.pagerState]);
            this.html = values.html;
            this.buttons = values.buttons;
            this.search_filters = values.search_filters;
            this.records_count = values.records_count;
            this.pagerState = values.pagerState;

            if (this.report_ref.el) {
                this.report_ref.el.innerHTML = this.html;
            } 
        });

        onMounted(() => {
            if (this.report_ref.el) {
                this.report_ref.el.innerHTML = this.html;
                document.querySelectorAll('.o_product_link').forEach(link => {
                    link.addEventListener('click', self.open_product.bind(self));
                });
            } else {
                console.error('Report element not found during onMounted');
            }
        });

        browser.sessionStorage.setItem('pagerState', '{}');
    }

    focusInnerInput(selectedItem) {
        selectedItem.el.querySelector(":scope input")?.focus();
    }

    open_product(e) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: "product.product",
            res_id: parseInt(e.target.dataset.product),
            views: [[false, 'form']],
        });
    }

    get getGroupPagerProps() {
        const currentMinimum = this.pagerState.offset;
        const limit = this.pagerState.limit;
        const size = this.records_count;
        return {
            offset: currentMinimum,
            limit: limit,
            total: size,
            onUpdate: async ({ offset, limit }) => {
                browser.sessionStorage.setItem('pagerState', JSON.stringify({
                    limit: limit,
                    offset: offset,
                }));
                  await this.getHtml(this.search_filters);
            },
            withAccessKey: false,
        };
    }

    get filters() {
        return this.search_filters;
    }

    get i18n() {
        return {
            onlyWithMovements: _t("Only with movements"),
            today: _t("Today"),
            thisMonth: _t("This month"),
            thisWeek: _t("This week"),
            fromLabel: _t("From:"),
            toLabel: _t("to:"),
            customRange: _t("Custom date range"),
            until: _t("until"),
            apply: _t("Apply"),
            products: _t("Products"),
            categories: _t("Categories"),
            companyPrefix: _t("Company:"),
            selectCompany: _t("Select a company"),
            warehouse: _t("Warehouse"),
            locations: _t("Locations"),
            favorites: _t("Favorites"),
            edit: _t("Edit"),
            save: _t("Save"),
            delete: _t("Delete"),
            favoriteNamePlaceholder: _t("Favorite name"),
        };
    }

    get companyList() {
        return this.company_id;
    }

    get filteredCompanyList() {
        var companysList = []
        var self = this;
        for (var company_id of this.company_id){
            var company = self.allCompaniesList.find(c => c.id === company_id)
            if (company){
                if (!company.parent_id){
                    companysList.push(company_id)
                } else if (company.parent_id && !companysList.includes(company.parent_id[0])){
                    if (!self.company_id.includes(company.parent_id[0])){
                        companysList.push(company.parent_id[0])
                    }
                }
            }
        }
        return companysList;
    }

    get allCompaniesList() {
        return this.allCompanies;
    }

    get selectedCompanyId() {
        return this.search_filters.company_id;
    }

    get selectedCompanyName() {
        for (const company of this.allCompanies)
            if (company.id === this.search_filters.company_id)
                return company.name;
    }

    async filterCompany(companyId) {
        let option = this.search_filters;
        option['company_id'] = parseInt(companyId);
        await this.getHtml(this.search_filters);
    }

    async getHtml(filters) {
        const values = await this.orm.call('inventory.movement.report', 'get_html', [[this.report_id], this.search_filters, this.pagerState]);
        this.html = values.html;
        this.buttons = values.buttons;
        this.search_filters = values.search_filters;
        this.records_count = values.records_count;
        this.pagerState = values.pagerState;
        this.report_ref.el.innerHTML = this.html;
        browser.sessionStorage.setItem('inventory_movement_report_options', JSON.stringify(filters));
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'soft_reload',
            context: {'is_soft_reload': true},
            params: {model: "inventory"}
        });
    }

    _buildSearchFilters() {
        return {
            'date': {'filter': 'today', 'date_from': '', 'date_to': ''},
            'company_id': false,
            'products': [],
            'categories': [],
            'warehouses': [],
            'locations': [],
            'only_with_movements': true,
        }
    }

    async onOnlyMovementsToggle(ev) {
        this.search_filters.only_with_movements = ev.target.checked;
        await this.getHtml(this.search_filters);
    }

    displayNotification(text){
        this.notification.add(text, { type: "danger" });
    }

    async saveFavoriteClick(ev) {
        const input = document.querySelector("input[name='favorites']").value.trim();
        const model_name = this.report_model;
        if (input.trim() === "") {
            this.notification.add(_t("Please enter a valid title."), {
                type: "danger",
            });
            return;
        } else {
            const result = await this.rpc("/check/fav_menu", { 'res_id': false, 'favorites': input });
            if (result) {
                this.notification.add(_t("Favorite title should be unique."), {
                    type: "danger",
                });
            } else {
                await this.rpc("/web/save/favorites", {
                    'model_name': model_name,
                    'favorites': input,
                    'filter_options': this.search_filters,
                });
                await this.getHtml(this.search_filters);
            }
        }
    }

    async favClick(ev) {
        const target = ev.target;
        if (target.checked) {
            if (parseInt(this.currentFavorites) === parseInt(target.value)) {
                target.checked = false;
                this.currentFavorites = false;
                this.search_filters = this._buildSearchFilters();
                await this.getHtml(this.search_filters);
            } else {
                this.currentFavorites = target.value;
                const domainStr = target.dataset.filters;
                target.checked = true;
                this.search_filters = domainStr;
                await this.getHtml(this.search_filters);
            }
        } else if (this.currentFavorites === parseInt(target.value)) {
            target.checked = false;
            this.currentFavorites = false;
            this.search_filters = this._buildSearchFilters();
            await this.getHtml(this.search_filters);
        }
        browser.sessionStorage.setItem('currentFavorites', this.currentFavorites);
    }

    async actionPrint(action){
        var self = this;
        this.dialog.add(PrintConfirmationDialog, {
            title: _t("Confirmation"),
            body: _t("You can print report of Current page / All pages."),
            printsingle: () => {
                self.search_filters.pagerState = self.pagerState;
                self.orm.call('inventory.movement.report', action, [self.report_id,self.search_filters]).then(result => {
                    const data = JSON.stringify(result.data);
                    const url = '/action_report_print'
                        .replace(":active_id", self.context.active_id)
                        .replace(":active_model", self.context.model)
                        .replace("output_format", "pdf");
                    download({
                        data: { data },
                        url,
                    });
                });
            },
            printsingleLabel: _t('Print Current Page'),
            printall: () => {
                self.search_filters['pagerState'] = {'limit': self.records_count};
                self.orm.call('inventory.movement.report', action, [self.report_id,self.search_filters]).then(result => {
                    const data = JSON.stringify(result.data);
                    const url = '/action_report_print'
                        .replace(":active_id", self.context.active_id)
                        .replace(":active_model", self.context.model)
                        .replace("output_format", "pdf");
                    download({
                        data: { data },
                        url,
                    });
                });
            },
            printallLabel: _t('Print All Pages'),
            cancel: () => {},
            cancelLabel: _t("Cancel"),
        });
    }

    getMultiRecordSelectorProps(resModel, optionKey) {
        var self = this;
        return {
            resModel,
            resIds: this.search_filters[optionKey],
            update: (resIds) => {
                if (resIds.length > 0 && optionKey === 'products' && this.search_filters['categories'].length > 0){
                    this.orm.call('inventory.movement.report', 'search_read_categories', [[], this.search_filters['categories'], resIds]).then(function(categories){
                        self.search_filters['categories'] = categories;
                    });
                }
                if (resIds.length > 0 && optionKey === 'categories' && this.search_filters['products'].length > 0){
                    this.orm.call('inventory.movement.report', 'search_read_products', [[], this.search_filters['products'], resIds]).then(function(products){
                        self.search_filters['products'] = products;
                    });
                }
                if (resIds.length > 0 && optionKey === 'warehouses' && this.search_filters['locations'].length > 0){
                    this.orm.call('inventory.movement.report', 'search_read_locations', [[], this.search_filters['locations'], resIds]).then(function(locations){
                        self.search_filters['locations'] = locations;
                    });
                }
                this.updateFilter(optionKey, resIds);
            },
        };
    }

    async updateFilter(optionKey, optionValue) {
        await this.updateOption(optionKey, optionValue, true);
    }

    async _updateOption(operationType, optionPath, optionValue=null, reloadUI=false) {
        const optionKeys = optionPath.split(".");
        let currentOptionKey = null;
        let option = this.search_filters;
        while (optionKeys.length > 1) {
            currentOptionKey = optionKeys.shift();
            option = option[currentOptionKey];

            if (option  === undefined)
                throw new Error(`Invalid option key in _updateOption(): ${ currentOptionKey } (${ optionPath })`);
        }
        switch (operationType) {
            case "update":
                option[optionKeys[0]] = optionValue;
                break;
            case "delete":
                delete option[optionKeys[0]];
                break;
            case "toggle":
                option[optionKeys[0]] = !option[optionKeys[0]];
                break;
            default:
                throw new Error(`Invalid operation type in _updateOption(): ${ operationType }`);
        }

        if (reloadUI){
            var warning = false;
            if (optionValue == 'custom') {
                var date_from = this.search_filters['date'].date_from;
                var date_to = this.search_filters['date'].date_to;
                const date = new Date();
                if (date_from instanceof Object){
                    const year = date_from.year;
                    const month = String(date_from.month).padStart(2, '0');
                    const day = String(date_from.day).padStart(2, '0');
                    date_from = `${year}-${month}-${day}`;
                }
                if (date_to instanceof Object){
                    const year = date_to.year;
                    const month = String(date_to.month).padStart(2, '0');
                    const day = String(date_to.day).padStart(2, '0');
                    date_to = `${year}-${month}-${day}`;
                }
                if (date_from > date_to){
                    warning = true;
                    this.dialog.add(WarningDialog, {
                        title: _t("Warning"),
                        message: _t("To Date must be bigger than From Date!"),
                    });
                }
            }
            if (!warning){
                await this.getHtml(this.search_filters);
            }
        }
    }

    async updateOption(optionPath, optionValue, reloadUI=false) {
        await this._updateOption('update', optionPath, optionValue, reloadUI);
    }

    dateFrom(optionKey) {
        return DateTime.fromISO(this.search_filters[optionKey].date_from);
    }

    dateTo(optionKey) {
        return DateTime.fromISO(this.search_filters[optionKey].date_to);
    }

    localeDateFrom(optionKey) {
        return this.dateFrom(optionKey).toLocaleString(DateTime.DATE_MED);
    }

    localeDateTo(optionKey) {
        return this.dateTo(optionKey).toLocaleString(DateTime.DATE_MED);
    }

    setDate(optionKey, type, date) {
        if (date)
            this.search_filters[optionKey][`date_${type}`] = date;
        else
            this.dialog.add(WarningDialog, {
                title: _t("Odoo Warning"),
                message: _t("Date cannot be empty"),
            });
    }

    setDateFrom(optionKey, dateFrom) {
        this.setDate(optionKey, 'from', dateFrom);
    }

    setDateTo(optionKey, dateTo) {
        this.setDate(optionKey, 'to', dateTo);
    }

    get evaluatedLocationDomain() {
        const domain = [['usage', '=', 'internal']];
        if (this.search_filters['warehouses'].length > 0) {
            domain.push('|')
            domain.push(['warehouse_id', '=', false])
            domain.push(['warehouse_id', 'in', this.search_filters['warehouses']])
        }
        if (this.search_filters['company_id']) {
            domain.push('|')
            domain.push(['company_id', '=', false])
            domain.push(['company_id', '=', this.search_filters['company_id']])
        }
        return domain;
    }

    get evaluatedWarehouseDomain() {
        const domain = [];
        if (this.search_filters['company_id']) {
            domain.push('|')
            domain.push(['company_id', '=', false])
            domain.push(['company_id', '=', this.search_filters['company_id']])
        }
        return domain;
    }

    get dropdownProps() {
        return {
            shouldFocusChildInput: false,
            hotkeys: {
                arrowright: (navigator) => this.focusInnerInput(navigator.activeItem),
            },
        };
    }

    async deleteClick(record) {
        this.dialog.add(DeleteFavouriteRecord, {
            title: _t("Warning"),
            body: _t("Are you sure you want to delete this favorite record?"),
            resId: parseInt(record),
        });
    }

    async editClick(ev) {
        // To edit favoritte link
        const parent = ev.target.closest('li');
        if (parent) {
            const favListInput = parent.querySelector("input[name='fav_list']");
            const editNameReadonlyInput = parent.querySelector("input[name='edit_name_readonly']");
            const editNameInput = parent.querySelector("input[name='edit_name']");

            if (favListInput) favListInput.style.position = 'unset';
            if (editNameReadonlyInput) editNameReadonlyInput.style.display = 'none';
            if (editNameInput) editNameInput.classList.remove('d-none');
        }
    }

    async saveClick(ev) {
        // To save favoritte link
        const self = this;
        const $resId = ev.target.getAttribute('data-id');

        const parent = ev.target.closest('li');

        if (parent) {
            const favListInput = parent.querySelector("input[name='fav_list']");
            const editNameReadonlyInput = parent.querySelector("input[name='edit_name_readonly']");
            const editNameInput = parent.querySelector("input[name='edit_name']");

            if (favListInput) favListInput.style.position = 'absolute';
            if (editNameReadonlyInput) editNameReadonlyInput.style.display = 'block';
            if (editNameInput) editNameInput.classList.add('d-none');

            const input_val = editNameInput ? editNameInput.value : '';

            if (input_val) {
                self.rpc("/check/fav_menu", {
                    'res_id': $resId,
                    'favorites': input_val,
                }).then(async function (result) {
                    if (result) {
                        self.displayNotification(_t("Favorite title should be unique."));
                    } else {
                        if (editNameReadonlyInput) editNameReadonlyInput.value = input_val;
                        self.rpc("/save/fav_menu", {
                            'res_id': $resId,
                            'favorites': input_val,
                        }).then(async function () {
                            await self.getHtml(self.search_filters);
                        });
                    }
                });
            } else {
                self.displayNotification(_t("Favorite title shouldn't be blank."));
            }
        }
    }

}

registry.category("actions").add("inventory_movement_report", StockMovementReportAction);
