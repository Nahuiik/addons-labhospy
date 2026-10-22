/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";
import { useService } from "@web/core/utils/hooks";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";

const { DateTime } = luxon;
const DEBOUNCE_MS = 400;

export class BiAccountReportFilters extends Component {
    static template = "bi_financial_reports_comm.BiAccountReportFilters";
    static components = { DateTimeInput, Dropdown, DropdownItem, MultiRecordSelector };
    static props = {};

    get _t() {
        return _t;
    }

    setup() {
        const self = this;
        this.controller = useState(this.env.controller);
        this.partnerFilterDebounce = null;
        this.tagFilterDebounce = null;
        this.accountFilterDebounce = null;
        this.analyticFilterDebounce = null;
        this.journalList = useState([]);
        this.reportCurrencyList = useState([]);
        this.savedFiltersList = useState([]);
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dateFromPicker = useDateTimePicker({
            target: "dateFrom",
            startDateRefName: "dateFrom",
            endDateRefName: "dateFrom",
            get pickerProps() {
                const d = self.env.controller.state.options.date_from;
                return {
                    value: d ? DateTime.fromISO(d) : null,
                    type: "date",
                };
            },
            onApply: (date) => {
                if (date) {
                    self.env.controller.setOptions({ date_from: date.toISODate() });
                }
            },
        });
        this.dateToPicker = useDateTimePicker({
            target: "dateTo",
            startDateRefName: "dateTo",
            endDateRefName: "dateTo",
            get pickerProps() {
                const d = self.env.controller.state.options.date_to;
                return {
                    value: d ? DateTime.fromISO(d) : null,
                    type: "date",
                };
            },
            onApply: (date) => {
                if (date) {
                    self.env.controller.setOptions({ date_to: date.toISODate() });
                }
            },
        });
        this.partnerAgeingDatePicker = useDateTimePicker({
            target: "partnerAgeingDate",
            startDateRefName: "partnerAgeingDate",
            endDateRefName: "partnerAgeingDate",
            get pickerProps() {
                const d = self.env.controller.state.options.date_to;
                return {
                    value: d ? DateTime.fromISO(d) : null,
                    type: "date",
                };
            },
            onApply: (date) => {
                if (date) {
                    self.env.controller.setOptions({ date_to: date.toISODate() });
                }
            },
        });
        onWillStart(async () => {
            const needsJournals =
                this.env.reportType === "general_ledger" ||
                this.env.reportType === "partner_ledger" ||
                this.env.reportType === "trial_balance" ||
                this.env.reportType === "profit_loss" ||
                this.env.reportType === "profit_and_loss" ||
                this.env.reportType === "balance_sheet" ||
                this.env.reportType === "analytic_report" ||
                this.env.reportType === "executive_summary" ||
                this.env.reportType === "cash_flow" ||
                this.env.reportType === "tax_report" ||
                this.env.reportType === "tax_return";
            if (needsJournals) {
                const journals = await this.orm.searchRead(
                    "account.journal",
                    [],
                    ["id", "code", "name"],
                    { order: "code" }
                );
                this.journalList.push(...journals);
            }
            if (
                [
                    "balance_sheet",
                    "profit_loss",
                    "profit_and_loss",
                    "trial_balance",
                    "cash_flow",
                    "tax_report",
                    "tax_return",
                    "executive_summary",
                ].includes(this.env.reportType)
            ) {
                const curs = await this.orm.searchRead(
                    "res.currency",
                    [["active", "=", true]],
                    ["id", "name", "symbol"],
                    { order: "name" }
                );
                this.reportCurrencyList.push(...curs);
            }
            if (this.supportsSavedFilters) {
                await this.refreshSavedFiltersList();
            }
        });
    }

    onDateFromClick() {
        this.dateFromPicker.open();
    }

    onDateToClick() {
        this.dateToPicker.open();
    }

    onPartnerAgeingDateClick() {
        this.partnerAgeingDatePicker.open();
    }

    get dateFromLabel() {
        const d = this.controller.state.options.date_from;
        return d ? DateTime.fromISO(d).toLocaleString(DateTime.DATE_SHORT) : _t("Select");
    }

    get dateToLabel() {
        const d = this.controller.state.options.date_to;
        return d ? DateTime.fromISO(d).toLocaleString(DateTime.DATE_SHORT) : _t("Select");
    }

    get customDateRangeLabel() {
        const from = this.controller.state.options.date_from;
        const to = this.controller.state.options.date_to;
        if (from && to) {
            const fromStr = DateTime.fromISO(from).toLocaleString(DateTime.DATE_SHORT);
            const toStr = DateTime.fromISO(to).toLocaleString(DateTime.DATE_SHORT);
            return `${fromStr} ${_t("para")} ${toStr}`;
        }
        return _t("Select");
    }

    get partnerAgeingDateLabel() {
        const d = this.controller.state.options.date_to;
        return d ? DateTime.fromISO(d).toLocaleString(DateTime.DATE_SHORT) : _t("As of");
    }

    get hasGeneralLedgerFilters() {
        return this.env.reportType === "general_ledger";
    }

    get hasPartnerLedgerFilters() {
        return this.env.reportType === "partner_ledger";
    }

    get hasReportSwitcher() {
        return (
            this.env.reportType === "partner_ledger" ||
            this.env.reportType === "partner_ageing"
        );
    }

    get reportOptions() {
        return [
            { id: "partner_ledger", name: _t("Libro mayor de la empresa"), action: "bi_financial_reports_comm.partner_ledger_action" },
            { id: "customer_statement", name: _t("Estado de cuenta del cliente"), action: "bi_financial_reports_comm.customer_statement_action" },
            { id: "partner_ageing_receivable", name: _t("Cuenta por cobrar vencida"), action: "bi_financial_reports_comm.partner_ageing_receivable_action" },
            { id: "partner_ageing_payable", name: _t("Cuenta por pagar vencida"), action: "bi_financial_reports_comm.partner_ageing_payable_action" },
        ];
    }

    get reportSwitcherLabel() {
        if (this.env.reportType === "partner_ageing") {
            return _t("Reporte de seguimiento");
        }
        if (this.env.reportVariant === "customer_statement") {
            return _t("Estado de cuenta del cliente");
        }
        return _t("Libro mayor de la empresa");
    }

    isReportSelected(id) {
        if (id === "partner_ageing_receivable") {
            return this.env.reportType === "partner_ageing"
                && this.controller?.state?.options?.account_type === "receivable";
        }
        if (id === "partner_ageing_payable") {
            return this.env.reportType === "partner_ageing"
                && this.controller?.state?.options?.account_type === "payable";
        }
        if (id === "customer_statement") return this.env.reportVariant === "customer_statement";
        return this.env.reportType === "partner_ledger" && !this.env.reportVariant;
    }

    onReportSelect(actionXmlId) {
        this.actionService.doAction(actionXmlId);
    }

    get hasTrialBalanceFilters() {
        return this.env.reportType === "trial_balance";
    }

    get hasProfitLossFilters() {
        return this.env.reportType === "profit_loss" || this.env.reportType === "profit_and_loss";
    }

    get hasBalanceSheetFilters() {
        return this.env.reportType === "balance_sheet";
    }

    get hasAnalyticFilters() {
        return (
            this.hasBalanceSheetFilters ||
            this.hasProfitLossFilters ||
            this.hasTrialBalanceFilters ||
            this.hasCashFlowFilters ||
            this.hasExecutiveSummaryFilters ||
            this.hasTaxReportFilters
        );
    }

    get hasExecutiveSummaryFilters() {
        return this.env.reportType === "executive_summary";
    }

    get hasAnalyticReportFilters() {
        return this.env.reportType === "analytic_report";
    }

    get hasPeriodDateFilter() {
        return (
            this.env.reportType === "general_ledger" ||
            this.env.reportType === "partner_ledger" ||
            this.env.reportType === "trial_balance" ||
            this.env.reportType === "profit_loss" ||
            this.env.reportType === "profit_and_loss" ||
            this.env.reportType === "balance_sheet" ||
            this.env.reportType === "analytic_report" ||
            this.env.reportType === "executive_summary" ||
            this.env.reportType === "cash_flow" ||
            this.env.reportType === "bank_reconciliation" ||
            this.env.reportType === "tax_report" ||
            this.env.reportType === "tax_return"
        );
    }

    get hasTaxReportFilters() {
        return this.env.reportType === "tax_report" || this.env.reportType === "tax_return";
    }

    get taxReportOptionsLabel() {
        return this._financialReportOptionsLabel();
    }

    isTaxReportOptionSelected(key) {
        const opts = this.controller.state.options;
        if (key === "include_draft") return opts.target_move === "all";
        if (key === "hierarchy") {
            return opts.hierarchy === undefined ? true : !!opts.hierarchy;
        }
        if (key === "unfold_all") return !!opts.unfold_all;
        if (key === "hide_zero_lines") return !!opts.hide_zero_lines;
        return false;
    }

    onTaxReportOptionToggle(key) {
        const opts = this.controller.state.options;
        if (key === "include_draft") {
            const next = opts.target_move === "all" ? "posted" : "all";
            this.controller.setOptions({ target_move: next });
            return;
        }
        if (key === "hierarchy") {
            const cur = opts.hierarchy === undefined ? true : !!opts.hierarchy;
            this.controller.setOptions({ hierarchy: !cur });
            return;
        }
        if (key === "unfold_all") {
            this.controller.setOptions({ unfold_all: !opts.unfold_all });
            return;
        }
        if (key === "hide_zero_lines") {
            this.controller.setOptions({ hide_zero_lines: !opts.hide_zero_lines });
            return;
        }
    }

    get hasCashFlowFilters() {
        return this.env.reportType === "cash_flow";
    }

    get hasBankReconciliationFilters() {
        return this.env.reportType === "bank_reconciliation";
    }

    get cashFlowOptionsLabel() {
        return this._financialReportOptionsLabel();
    }

    get executiveSummaryOptionsLabel() {
        return this._financialReportOptionsLabel();
    }

    get cashFlowEntryOptions() {
        return [
            { id: "all_entries", name: _t("Borradores de asientos") },
            { id: "hierarchy", name: _t("Jerarquía y subtotales") },
            { id: "unfold_all", name: _t("Desplegar todo") },
            { id: "hide_zero_lines", name: _t("Oculta las líneas en 0") },
        ];
    }

    isCashFlowOptionSelected(id) {
        const opts = this.controller.state.options;
        if (id === "all_entries") return opts.target_move === "all";
        if (id === "hierarchy") return !!opts.hierarchy;
        if (id === "unfold_all") return !!opts.unfold_all;
        if (id === "hide_zero_lines") return !!opts.hide_zero_lines;
        return false;
    }

    onCashFlowOptionToggle(id) {
        const opts = { ...this.controller.state.options };
        if (id === "all_entries") {
            opts.target_move = opts.target_move === "all" ? "posted" : "all";
            this.controller.setOptions(opts);
            return;
        }
        if (id === "hierarchy") {
            this.controller.setOptions({ hierarchy: !opts.hierarchy });
            return;
        }
        if (id === "unfold_all") {
            this.controller.toggleUnfoldAll();
            return;
        }
        if (id === "hide_zero_lines") {
            this.controller.setOptions({ hide_zero_lines: !opts.hide_zero_lines });
            return;
        }
    }

    get dateFilterType() {
        return this.controller.state.options.date_filter_type || "month";
    }

    get dateFilterReference() {
        const ref = this.controller.state.options.date_filter_reference;
        return ref ? DateTime.fromISO(ref) : DateTime.now();
    }

    get periodDateFilterLabel() {
        const opts = this.controller.state.options;
        const type = opts.date_filter_type || "month";
        if (type === "custom") {
            const from = opts.date_from
                ? DateTime.fromISO(opts.date_from).toLocaleString(DateTime.DATE_SHORT)
                : "";
            const to = opts.date_to
                ? DateTime.fromISO(opts.date_to).toLocaleString(DateTime.DATE_SHORT)
                : "";
            return from && to ? `${from} ${_t("para")} ${to}` : _t("Fechas personalizadas");
        }
        const dt = this.dateFilterReference;
        if (type === "month") {
            return this.periodMonthLabel;
        }
        if (type === "quarter") {
            const qStart = dt.startOf("quarter");
            const qEnd = dt.endOf("quarter");
            const fromStr = qStart.toLocaleString({ month: "short" });
            const toStr = qEnd.toLocaleString({ month: "short", year: "numeric" });
            return `${fromStr} - ${toStr}`;
        }
        return dt.toLocaleString({ year: "numeric" });
    }

    get periodMonthLabel() {
        const dt = this.dateFilterReference;
        const month = dt.toLocaleString({ month: "long" });
        const capitalized = month.charAt(0).toUpperCase() + month.slice(1);
        return `${capitalized} ${dt.year}`;
    }

    get periodQuarterLabel() {
        const dt = this.dateFilterReference;
        const qStart = dt.startOf("quarter");
        const qEnd = dt.endOf("quarter");
        const fromStr = qStart.toLocaleString({ month: "short" });
        const toStr = qEnd.toLocaleString({ month: "short", year: "numeric" });
        return `${fromStr} - ${toStr}`;
    }

    get periodYearLabel() {
        return this.dateFilterReference.toLocaleString({ year: "numeric" });
    }

    _computeDatesFromPeriod(type, refDt) {
        if (type === "month") {
            return [
                refDt.startOf("month").toISODate(),
                refDt.endOf("month").toISODate(),
            ];
        }
        if (type === "quarter") {
            return [
                refDt.startOf("quarter").toISODate(),
                refDt.endOf("quarter").toISODate(),
            ];
        }
        if (type === "year") {
            return [
                refDt.startOf("year").toISODate(),
                refDt.endOf("year").toISODate(),
            ];
        }
        return null;
    }

    onDateFilterTypeChange(type) {
        const ref = this.dateFilterReference;
        const [date_from, date_to] = this._computeDatesFromPeriod(type, ref);
        this.env.controller.setOptions({
            date_filter_type: type,
            date_filter_reference: ref.toISODate(),
            date_from,
            date_to,
        });
    }

    onDateFilterNav(ev, type, delta) {
        ev.preventDefault();
        ev.stopPropagation();
        const ref = this.dateFilterReference;
        let newRef;
        if (type === "month") {
            newRef = ref.plus({ months: delta });
        } else if (type === "quarter") {
            newRef = ref.plus({ quarters: delta });
        } else {
            newRef = ref.plus({ years: delta });
        }
        const [date_from, date_to] = this._computeDatesFromPeriod(type, newRef);
        this.env.controller.setOptions({
            date_filter_type: type,
            date_filter_reference: newRef.toISODate(),
            date_from,
            date_to,
        });
    }

    onDateFilterCustomClick() {
        const opts = this.controller.state.options;
        this.controller.setOptions({
            date_filter_type: "custom",
            date_filter_reference: opts.date_to || opts.date_from || DateTime.now().toISODate(),
        });
    }

    get customDateFrom() {
        const d = this.controller.state.options.date_from;
        return d ? DateTime.fromISO(d) : DateTime.now().startOf("month");
    }

    get customDateTo() {
        const d = this.controller.state.options.date_to;
        return d ? DateTime.fromISO(d) : DateTime.now().endOf("month");
    }

    setCustomDateFrom(date) {
        if (date) {
            this.controller.setOptions({ date_from: date.toISODate() });
        }
    }

    setCustomDateTo(date) {
        if (date) {
            this.controller.setOptions({ date_to: date.toISODate() });
        }
    }

    get hasPartnerAgeingFilters() {
        return this.env.reportType === "partner_ageing";
    }

    get hasReportCurrencyFilter() {
        return [
            "balance_sheet",
            "profit_loss",
            "profit_and_loss",
            "trial_balance",
            "cash_flow",
            "tax_report",
            "tax_return",
            "executive_summary",
        ].includes(this.env.reportType);
    }

    get supportsSavedFilters() {
        return [
            "general_ledger",
            "partner_ledger",
            "trial_balance",
            "profit_loss",
            "profit_and_loss",
            "balance_sheet",
            "cash_flow",
            "tax_report",
            "tax_return",
            "analytic_report",
            "executive_summary",
            "bank_reconciliation",
            "partner_ageing",
        ].includes(this.env.reportType);
    }

    async refreshSavedFiltersList() {
        const model = this.env.controller.modelName;
        const rows = await this.orm.call("ir.filters", "bi_financial_list_saved_filters", [model]);
        this.savedFiltersList.splice(0, this.savedFiltersList.length);
        this.savedFiltersList.push(...(rows || []));
    }

    async onSaveBiFilter() {
        const name = window.prompt(_t("Nombre del filtro a guardar"), "");
        if (!name || !String(name).trim()) {
            return;
        }
        const res = await this.orm.call("ir.filters", "bi_financial_save_options_filter", [
            this.env.controller.modelName,
            String(name).trim(),
            this.env.controller.state.options,
        ]);
        if (res && res.error) {
            this.notification.add(_t("No se pudo guardar el filtro"), { type: "danger" });
            return;
        }
        this.notification.add(_t("Filtro guardado"), { type: "success" });
        await this.refreshSavedFiltersList();
    }

    async onApplyBiFilter(filterId) {
        const opts = await this.orm.call("ir.filters", "bi_financial_load_filter", [filterId]);
        if (!opts || typeof opts !== "object") {
            this.notification.add(_t("No se pudo cargar el filtro"), { type: "danger" });
            return;
        }
        await this.env.controller.setOptions(opts);
    }

    async onDeleteBiFilter(filterId, ev) {
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }
        const ok = await this.orm.call("ir.filters", "bi_financial_delete_filter", [filterId]);
        if (!ok) {
            this.notification.add(_t("No se pudo eliminar el filtro"), { type: "warning" });
            return;
        }
        await this.refreshSavedFiltersList();
        this.notification.add(_t("Filtro eliminado"), { type: "info" });
    }

    get reportCurrencyButtonLabel() {
        const id = this.controller.state.options.report_currency_id;
        if (!id) {
            return _t("Moneda del informe");
        }
        const c = this.reportCurrencyList.find((x) => x.id === id);
        return c ? `${c.name}` : _t("Moneda del informe");
    }

    isReportCurrencySelected(curId) {
        return this.controller.state.options.report_currency_id === curId;
    }

    onReportCurrencyPick(curId) {
        this.controller.setOptions({ report_currency_id: curId });
    }

    onReportCurrencyClear() {
        this.controller.setOptions({ report_currency_id: null });
    }

    get hasTargetMoveFilter() {
        return (
            this.env.reportType === "general_ledger" ||
            this.env.reportType === "partner_ledger" ||
            this.env.reportType === "partner_ageing"
        );
    }

    get accountTypeLabel() {
        if (this.env.reportType === "partner_ledger") {
            const ids = this.controller.state.options.account_type_ids || [];
            const names = {
                trade_receivable: _t("Por cobrar"),
                non_trade_receivable: _t("Cuentas por cobrar no comerciales"),
                trade_payable: _t("Por pagar"),
                non_trade_payable: _t("Cuentas por pagar no comerciales"),
            };
            if (ids.length === 0) return _t("Por cobrar");
            if (ids.length === 2 && ids.includes("trade_receivable") && ids.includes("trade_payable")) {
                return _t("Por cobrar y por pagar");
            }
            return ids.map((id) => names[id] || id).join(", ") || _t("Por cobrar");
        }
        // partner_ageing (y otros que usen account_type both/receivable/payable)
        const map = {
            both: _t("Por cobrar y por pagar"),
            receivable: _t("Por cobrar"),
            payable: _t("Por pagar"),
        };
        return map[this.controller.state.options.account_type] || map.both;
    }

    get accountTypeOptions() {
        return [
            { id: "trade_receivable", name: _t("Por cobrar") },
            { id: "non_trade_receivable", name: _t("Cuentas por cobrar no comerciales") },
            { id: "trade_payable", name: _t("Por pagar") },
            { id: "non_trade_payable", name: _t("Cuentas por pagar no comerciales") },
        ];
    }

    isAccountTypeSelected(id) {
        const ids = this.controller.state.options.account_type_ids || [];
        return ids.includes(id);
    }

    onAccountTypeToggle(id) {
        const ids = [...(this.controller.state.options.account_type_ids || [])];
        const idx = ids.indexOf(id);
        if (idx >= 0) ids.splice(idx, 1);
        else ids.push(id);
        this.controller.setOptions({ account_type_ids: ids });
    }

    get basedOnLabel() {
        const map = { due: _t("Due Date"), invoice: _t("Invoice Date") };
        return map[this.controller.state.options.based_on] || map.due;
    }

    get periodLengthLabel() {
        const n = this.controller.state.options.period_length;
        return n ? `${n} ${_t("days")}` : "30 " + _t("days");
    }

    get targetMoveLabel() {
        const map = { posted: _t("Posted"), all: _t("All") };
        return map[this.controller.state.options.target_move] || map.all;
    }

    get entriesOptions() {
        return [
            { id: "all_entries", name: _t("Borradores de asientos") },
            { id: "hierarchy", name: _t("Jerarquía y subtotales") },
            { id: "unreconciled", name: _t("Asientos sin conciliar") },
            { id: "unfold_all", name: _t("Desplegar todo") },
        ];
    }

    /** Opciones estilo Enterprise (Balance, P&L, Balance de comprobación) */
    get financialReportExtraOptions() {
        const options = [
            { id: "all_entries", name: _t("Borradores de asientos") },
        ];
        if (this.hasAnalyticFilters) {
            options.push({ id: "include_analytic_without_aml", name: _t("Simulaciones analíticas") });
        }
        options.push(
            { id: "hierarchy", name: _t("Jerarquía y subtotales") },
            { id: "unfold_all", name: _t("Desplegar todo") },
            { id: "report_cash_basis", name: _t("Método de base de efectivo") },
            { id: "_divider_ui", divider: true },
            { id: "hide_zero_lines", name: _t("Ocultar las líneas en 0"), uiOnly: true },
        );
        if (this.hasBalanceSheetFilters) {
            options.push({ id: "horizontal_split", name: _t("Dividir horizontalmente"), uiOnly: true });
            options.push({ id: "show_fx_balance", name: _t("Mostrar importe en moneda de la cuenta") });
        }
        return options;
    }

    isFinancialReportOptionSelected(id) {
        const opts = this.controller.state.options;
        if (id === "all_entries") return opts.target_move === "all";
        if (id === "include_analytic_without_aml") return !!opts.include_analytic_without_aml;
        if (id === "hierarchy") return !!opts.hierarchy;
        if (id === "unfold_all") return !!opts.unfold_all;
        if (id === "report_cash_basis") return !!opts.report_cash_basis;
        if (id === "hide_zero_lines") return !!opts.hide_zero_lines;
        if (id === "horizontal_split") return !!opts.horizontal_split;
        if (id === "show_fx_balance") return !!opts.show_fx_balance;
        return false;
    }

    onFinancialReportOptionToggle(id) {
        const opts = { ...this.controller.state.options };
        if (id === "all_entries") {
            opts.target_move = opts.target_move === "all" ? "posted" : "all";
            this.controller.setOptions(opts);
            return;
        }
        if (id === "include_analytic_without_aml") {
            this.controller.setOptions({ include_analytic_without_aml: !opts.include_analytic_without_aml });
            return;
        }
        if (id === "hierarchy") {
            this.controller.setOptions({ hierarchy: !opts.hierarchy });
            return;
        }
        if (id === "unfold_all") {
            this.controller.toggleUnfoldAll();
            return;
        }
        if (id === "report_cash_basis") {
            this.controller.setOptions({ report_cash_basis: !opts.report_cash_basis });
            return;
        }
        if (id === "hide_zero_lines") {
            this.controller.setOptions({ hide_zero_lines: !opts.hide_zero_lines }, { reload: false });
            return;
        }
        if (id === "horizontal_split") {
            this.controller.setOptions({ horizontal_split: !opts.horizontal_split }, { reload: false });
            return;
        }
        if (id === "show_fx_balance") {
            this.controller.setOptions({ show_fx_balance: !opts.show_fx_balance });
        }
    }

    _financialReportOptionsLabel() {
        const opts = this.controller.state.options;
        const parts = [
            opts.target_move === "posted" ? _t("Asientos registrados") : _t("Borradores incluidos"),
            opts.report_cash_basis ? _t("Base de efectivo") : _t("Base de acumulación"),
        ];
        if (opts.include_analytic_without_aml) {
            parts.push(_t("Simulaciones analíticas"));
        }
        if (opts.hide_zero_lines) {
            parts.push(_t("Sin ceros"));
        }
        if (opts.horizontal_split) {
            parts.push(_t("Dividido"));
        }
        return parts.join(", ");
    }

    /** Jerarquía + Desplegar todo (Balance, Estado de resultados, Balance de comprobación) — estilo Enterprise */
    get hierarchyUnfoldOptions() {
        return [
            { id: "hierarchy", name: _t("Jerarquía y subtotales") },
            { id: "unfold_all", name: _t("Desplegar todo") },
        ];
    }

    isEntryOptionSelected(id) {
        const opts = this.controller.state.options;
        if (id === "all_entries") return opts.target_move === "all";
        if (id === "hierarchy") return !!opts.hierarchy;
        if (id === "unreconciled") return !!opts.unreconciled;
        if (id === "unfold_all") return !!opts.unfold_all;
        return false;
    }

    onEntryOptionToggle(id) {
        const opts = { ...this.controller.state.options };
        if (id === "all_entries") {
            opts.target_move = opts.target_move === "all" ? "posted" : "all";
            this.controller.setOptions(opts);
            return;
        }
        if (id === "hierarchy") {
            opts.hierarchy = !opts.hierarchy;
            this.controller.setOptions(opts);
            return;
        }
        if (id === "unreconciled") {
            opts.unreconciled = !opts.unreconciled;
            this.controller.setOptions(opts);
            return;
        }
        if (id === "unfold_all") {
            this.controller.toggleUnfoldAll();
            return;
        }
    }

    get optionsFilterLabel() {
        const opts = this.controller.state.options;
        const displayMap = {
            all: _t("All"),
            movement: _t("Con Movimientos"),
            not_zero: _t("Con balance distinto de cero"),
        };
        const displayLabel = displayMap[opts.display_account] || displayMap.movement;
        return `${this._financialReportOptionsLabel()}, ${displayLabel}`;
    }

    get trialBalanceOptionsLabel() {
        const opts = this.controller.state.options;
        const displayMap = {
            all: _t("Todas"),
            movement: _t("Con movimientos"),
            not_zero: _t("Con balance distinto de cero"),
        };
        const displayLabel = displayMap[opts.display_account] || displayMap.movement;
        return `${this._financialReportOptionsLabel()}, ${displayLabel}`;
    }

    get profitLossOptionsLabel() {
        return this._financialReportOptionsLabel();
    }

    get balanceSheetOptionsLabel() {
        return this._financialReportOptionsLabel();
    }

    get partnerNameFilter() {
        return this.controller.state.options.partner_name_filter || "";
    }

    get partnerTagNameFilter() {
        return this.controller.state.options.partner_tag_name_filter || "";
    }

    get accountFilter() {
        return this.controller.state.options.account_filter || "";
    }

    get journalFilterLabel() {
        const ids = this.controller.state.options.journal_ids || [];
        if (!ids.length) return _t("Todos los diarios");
        const names = ids
            .map((id) => this.journalList.find((x) => x.id === id))
            .filter(Boolean)
            .map((j) => `${j.code} - ${j.name}`);
        if (names.length <= 2) return names.join(", ");
        return `${names.length} ${_t("journals")}`;
    }

    isJournalSelected(journalId) {
        const ids = this.controller.state.options.journal_ids || [];
        return ids.includes(journalId);
    }

    onJournalToggle(ev, journalId) {
        const ids = [...(this.controller.state.options.journal_ids || [])];
        const idx = ids.indexOf(journalId);
        if (idx >= 0) ids.splice(idx, 1);
        else ids.push(journalId);
        this.controller.setOptions({ journal_ids: ids });
    }

    onJournalSelectAll() {
        this.controller.setOptions({
            journal_ids: this.journalList.map((j) => j.id),
        });
    }

    onJournalClearAll() {
        this.controller.setOptions({ journal_ids: [] });
    }

    onTargetMoveSet(val) {
        this.controller.setOptions({ target_move: val });
    }

    onDisplayAccountSet(val) {
        this.controller.setOptions({ display_account: val });
    }

    onToggleShowFxBalance() {
        const next = !this.controller.state.options.show_fx_balance;
        this.controller.setOptions({ show_fx_balance: next });
    }

    get comparisonFilterLabel() {
        const filter = this.controller.state.options.comparison_filter || "no_comparison";
        const labels = {
            no_comparison: _t("Comparación"),
            previous_period: _t("Periodo anterior"),
            same_last_year: _t("Mismo periodo el año anterior"),
            specific_date: _t("Fecha específica"),
        };
        const base = labels[filter] || _t("Comparación");
        if (filter === "specific_date" && this.controller.state.options.comparison_date_to) {
            const d = this.controller.state.options.comparison_date_to;
            const dt = DateTime.fromISO(d);
            return `${base}: ${dt.toLocaleString(DateTime.DATE_SHORT)}`;
        }
        return base;
    }

    onComparisonFilterSet(filter) {
        const opts = { comparison_filter: filter };
        if (filter === "specific_date" && !this.controller.state.options.comparison_date_to) {
            const ref = this.controller.state.options.date_to || DateTime.now().toISODate();
            const dt = DateTime.fromISO(ref);
            opts.comparison_date_to = dt.minus({ months: 1 }).endOf("month").toISODate();
        }
        this.controller.setOptions(opts);
    }

    get comparisonSpecificDate() {
        const d = this.controller.state.options.comparison_date_to;
        return d ? DateTime.fromISO(d) : DateTime.now().minus({ months: 1 }).endOf("month");
    }

    onComparisonSpecificDateChange(date) {
        if (date) {
            this.controller.setOptions({
                comparison_filter: "specific_date",
                comparison_date_to: date.toISODate(),
            });
        }
    }

    get comparisonPeriodOrder() {
        return this.controller.state.options.comparison_period_order || "descending";
    }

    onComparisonPeriodOrderChange(ev) {
        const val = ev.target?.value || "descending";
        this.controller.setOptions({ comparison_period_order: val });
    }

    get comparisonNumberPeriod() {
        const n = parseInt(this.controller.state.options.comparison_number_period, 10);
        return Number.isFinite(n) && n >= 1 ? n : 1;
    }

    onComparisonNumberPeriodChange(ev) {
        const n = parseInt(ev.target?.value, 10);
        if (!Number.isFinite(n) || n < 1) {
            return;
        }
        this.controller.setOptions({ comparison_number_period: n });
    }

    get comparisonPeriodUnitLabel() {
        const t = this.controller.state.options.date_filter_type || "month";
        if (t === "quarter") return _t("Trimestre");
        if (t === "year") return _t("Año");
        return _t("Período");
    }

    get analyticFilter() {
        return this.controller.state.options.analytic_filter || "";
    }

    onAnalyticFilterInput(ev) {
        const value = ev.target.value || "";
        if (this.analyticFilterDebounce) clearTimeout(this.analyticFilterDebounce);
        this.analyticFilterDebounce = setTimeout(() => {
            this.controller.setOptions({ analytic_filter: value });
            this.analyticFilterDebounce = null;
        }, DEBOUNCE_MS);
    }

    get analyticAccountSelectorProps() {
        return {
            resIds: this.controller.state.options.analytic_account_ids || [],
            resModel: "account.analytic.account",
            update: (ids) => this.controller.setOptions({ analytic_account_ids: ids }),
            placeholder: _t("Cuentas analíticas..."),
        };
    }

    get analyticPlanSelectorProps() {
        return {
            resIds: this.controller.state.options.plan_ids || [],
            resModel: "account.analytic.plan",
            update: (ids) => this.controller.setOptions({ plan_ids: ids }),
            placeholder: _t("Planes analíticos..."),
        };
    }

    get analyticFilterLabel() {
        const accounts = (this.controller.state.options.analytic_account_ids || []).length;
        const plans = (this.controller.state.options.plan_ids || []).length;
        const total = accounts + plans;
        if (total > 0) {
            return _t("Analítica") + " (" + total + ")";
        }
        return _t("Analítica");
    }

    /** Reports able to render analytic accounts as columns (matrix layout). */
    get supportsAnalyticColumns() {
        return [
            "profit_loss",
            "profit_and_loss",
            "balance_sheet",
            "trial_balance",
        ].includes(this.env.reportType);
    }

    get analyticColumnsActive() {
        return !!this.controller.state.options.analytic_columns;
    }

    onToggleAnalyticColumns() {
        this.controller.setOptions({
            analytic_columns: !this.controller.state.options.analytic_columns,
        });
    }

    onAccountFilterInput(ev) {
        const value = ev.target.value || "";
        if (this.accountFilterDebounce) clearTimeout(this.accountFilterDebounce);
        this.accountFilterDebounce = setTimeout(() => {
            this.controller.setOptions({ account_filter: value });
            this.accountFilterDebounce = null;
        }, DEBOUNCE_MS);
    }

    async onDisplayAccountChange(ev) {
        const val = ev.target?.value ?? ev.currentTarget?.dataset?.value;
        if (val) await this.controller.setOptions({ display_account: val });
    }

    async onTargetMoveChange(ev) {
        const val = ev.target?.value ?? ev.currentTarget?.dataset?.value;
        if (val) await this.controller.setOptions({ target_move: val });
    }

    async onAccountTypeChange(ev) {
        const val = ev.target?.value ?? ev.currentTarget?.dataset?.value;
        if (val) await this.controller.setOptions({ account_type: val });
    }

    onAccountTypeSet(val) {
        this.controller.setOptions({ account_type: val });
    }

    async onBasedOnChange(ev) {
        const val = ev.target?.value ?? ev.currentTarget?.dataset?.value;
        if (val) await this.controller.setOptions({ based_on: val });
    }

    onBasedOnSet(val) {
        this.controller.setOptions({ based_on: val });
    }

    async onPeriodLengthChange(ev) {
        const raw = ev.target?.value ?? ev.currentTarget?.dataset?.value;
        const val = parseInt(raw, 10);
        if (!isNaN(val) && val >= 1) {
            await this.controller.setOptions({ period_length: val });
        }
    }

    onPeriodLengthSet(val) {
        if (val >= 1) {
            this.controller.setOptions({ period_length: val });
        }
    }

    onPartnerFilterInput(ev) {
        const value = ev.target.value || "";
        if (this.partnerFilterDebounce) clearTimeout(this.partnerFilterDebounce);
        this.partnerFilterDebounce = setTimeout(() => {
            this.controller.setOptions({ partner_name_filter: value });
            this.partnerFilterDebounce = null;
        }, DEBOUNCE_MS);
    }

    onTagFilterInput(ev) {
        const value = ev.target.value || "";
        if (this.tagFilterDebounce) clearTimeout(this.tagFilterDebounce);
        this.tagFilterDebounce = setTimeout(() => {
            this.controller.setOptions({ partner_tag_name_filter: value });
            this.tagFilterDebounce = null;
        }, DEBOUNCE_MS);
    }

    onOpenWizard() {
        this.controller.actionService.doAction(
            "bi_financial_reports_comm.action_partner_ageing_report",
            { target: "new" }
        );
    }
}
