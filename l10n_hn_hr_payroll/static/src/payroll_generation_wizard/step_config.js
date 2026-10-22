/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class StepConfig extends Component {
    static template = "l10n_hn_hr_payroll.StepConfig";
    static props = {
        config: Object,
        onConfigChange: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            companies: [],
            structures: [],
            payrollPeriods: [],
            schedulePayOptions: [],
        });

        onWillStart(async () => {
            await this.loadOptions();
        });
    }

    async loadOptions(companyId = null) {
        const cid = companyId ?? this.props.config?.company_id ?? null;
        const opts = await this.orm.call(
            "hr.payslip.run",
            "get_payroll_wizard_options",
            [],
            { company_id: cid }
        );
        this.state.companies = opts.companies || [];
        this.state.structures = opts.structures || [];
        this.state.schedulePayOptions = opts.schedule_pay_options || [];
        this.state.defaultStructureId = opts.default_structure_id || null;
        this.state.currentPeriod = opts.current_period || null;
        this.state.defaultCompanyId = opts.default_company_id || null;

        if (cid) {
            const periods = await this.orm.searchRead(
                "l10n.hn.payroll.period",
                [["company_id", "=", cid]],
                ["id", "name", "date_start", "date_end"],
                { order: "year desc, month desc, period_number desc", limit: 24 }
            );
            this.state.payrollPeriods = periods;
        } else {
            this.state.payrollPeriods = [];
        }

        // Si no hay compañía pero hay default, recargar con compañía por defecto
        if (!cid && opts.default_company_id) {
            return this.loadOptions(opts.default_company_id);
        }

        // Aplicar defaults: estructura, frecuencia, quincena en curso
        const updates = {};
        if (cid && opts.default_company_id && !this.props.config?.company_id) {
            updates.company_id = opts.default_company_id;
        }
        if (cid && opts.default_structure_id && !this.props.config?.structure_id) {
            const defStruct = (opts.structures || []).find(
                (s) => s.id === opts.default_structure_id
            );
            const schedulePay = defStruct?.schedule_pay || null;
            updates.structure_id = opts.default_structure_id;
            updates.schedule_pay = schedulePay;
            if (schedulePay === "bi-weekly" && opts.current_period) {
                updates.payroll_period_id = opts.current_period.id;
                updates.date_start = opts.current_period.date_start;
                updates.date_end = opts.current_period.date_end;
            }
        }
        if (Object.keys(updates).length) {
            this.props.onConfigChange({ ...this.props.config, ...updates });
        }
    }

    onCompanyChange = async (ev) => {
        const companyId = ev.target.value ? parseInt(ev.target.value, 10) : null;
        this.props.onConfigChange({
            ...this.props.config,
            company_id: companyId,
            structure_id: null,
        });
        await this.loadOptions(companyId);
    };

    onStructureChange = (ev) => {
        const structureId = ev.target.value ? parseInt(ev.target.value, 10) : null;
        const struct = this.state.structures.find((s) => s.id === structureId);
        const schedulePay = struct?.schedule_pay || null;
        const updates = { structure_id: structureId, schedule_pay: schedulePay };
        if (schedulePay === "bi-weekly" && this.state.currentPeriod) {
            updates.payroll_period_id = this.state.currentPeriod.id;
            updates.date_start = this.state.currentPeriod.date_start;
            updates.date_end = this.state.currentPeriod.date_end;
        } else if (schedulePay !== "bi-weekly") {
            updates.payroll_period_id = null;
        }
        this.props.onConfigChange({ ...this.props.config, ...updates });
    };

    onSchedulePayChange = (ev) => {
        const schedulePay = ev.target.value || null;
        this.props.onConfigChange({ ...this.props.config, schedule_pay: schedulePay });
    };

    onDateStartChange = (ev) => {
        const dateStart = ev.target.value || null;
        this.props.onConfigChange({ ...this.props.config, date_start: dateStart });
    };

    onDateEndChange = (ev) => {
        const dateEnd = ev.target.value || null;
        this.props.onConfigChange({ ...this.props.config, date_end: dateEnd });
    };

    onPayrollPeriodChange = (ev) => {
        const periodId = ev.target.value ? parseInt(ev.target.value, 10) : null;
        const period = this.state.payrollPeriods.find(p => p.id === periodId);
        this.props.onConfigChange({
            ...this.props.config,
            payroll_period_id: periodId,
            date_start: period ? period.date_start : this.props.config.date_start,
            date_end: period ? period.date_end : this.props.config.date_end,
        });
    };

    get canProceed() {
        const c = this.props.config;
        return c.company_id && c.structure_id && c.schedule_pay && c.date_start && c.date_end;
    }
}
