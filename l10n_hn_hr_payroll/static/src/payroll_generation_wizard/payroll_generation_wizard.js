/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { StepConfig } from "./step_config";
import { StepEmployees } from "./step_employees";
import { StepReview } from "./step_review";

export class PayrollGenerationWizard extends Component {
    static template = "l10n_hn_hr_payroll.PayrollGenerationWizard";
    static components = { StepConfig, StepEmployees, StepReview };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            step: 1,
            config: {
                company_id: null,
                structure_id: null,
                schedule_pay: null,
                date_start: null,
                date_end: null,
                payroll_period_id: null,
            },
            versions: [],
            selectedIds: {},
            searchQuery: "",
            loading: false,
            generating: false,
        });
    }

    get stepTitles() {
        return [
            { num: 1, label: "Configuración" },
            { num: 2, label: "Empleados" },
            { num: 3, label: "Revisar y generar" },
        ];
    }

    onConfigChange = (config) => {
        this.state.config = { ...config };
    };

    goToStep2 = async () => {
        if (!this.state.config.company_id || !this.state.config.structure_id ||
            !this.state.config.schedule_pay || !this.state.config.date_start || !this.state.config.date_end) {
            return;
        }
        this.state.loading = true;
        try {
            const versions = await this.orm.call(
                "hr.payslip.run",
                "get_payroll_version_list",
                [],
                {
                    date_start: this.state.config.date_start,
                    date_end: this.state.config.date_end,
                    structure_id: this.state.config.structure_id,
                    company_id: this.state.config.company_id,
                    schedule_pay: this.state.config.schedule_pay,
                    payroll_period_id: this.state.config.payroll_period_id,
                }
            );
            this.state.versions = versions || [];
            this.state.selectedIds = {};
            versions.forEach(v => { this.state.selectedIds[v.id] = true; });
            this.state.step = 2;
        } catch (e) {
            this.notification.add(
                e?.message || "Error al cargar empleados",
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    };

    onToggle = (versionId) => {
        this.state.selectedIds[versionId] = !this.state.selectedIds[versionId];
    };

    onToggleAll = () => {
        const filtered = this.getFilteredVersions();
        const allSelected = filtered.every(v => this.state.selectedIds[v.id]);
        filtered.forEach(v => {
            this.state.selectedIds[v.id] = !allSelected;
        });
    };

    getFilteredVersions() {
        const q = (this.state.searchQuery || "").toLowerCase().trim();
        if (!q) return this.state.versions;
        return this.state.versions.filter(v => {
            const emp = v.employee_id;
            const empName = Array.isArray(emp) ? emp[1] : (emp && emp.display_name) || "";
            const dept = v.department_id;
            const deptName = Array.isArray(dept) ? dept[1] : (dept && dept.display_name) || "";
            const job = v.job_id;
            const jobName = Array.isArray(job) ? job[1] : (job && job.display_name) || "";
            return (
                empName.toLowerCase().includes(q) ||
                deptName.toLowerCase().includes(q) ||
                jobName.toLowerCase().includes(q)
            );
        });
    }

    onSearchChange = (ev) => {
        this.state.searchQuery = ev.target.value;
    };

    goToStep3 = () => {
        const count = Object.values(this.state.selectedIds).filter(Boolean).length;
        if (count === 0) {
            this.notification.add("Seleccione al menos un empleado", { type: "warning" });
            return;
        }
        this.state.step = 3;
    };

    goBack = () => {
        this.state.step = Math.max(1, this.state.step - 1);
    };

    generate = async () => {
        const versionIds = Object.entries(this.state.selectedIds)
            .filter(([, sel]) => sel)
            .map(([id]) => parseInt(id, 10));
        if (!versionIds.length) {
            this.notification.add("Seleccione al menos un empleado", { type: "warning" });
            return;
        }
        this.state.generating = true;
        try {
            const rawRecord = this.buildRawRecord();
            const ids = await this.orm.create("hr.payslip.run", [rawRecord]);
            await this.orm.call("hr.payslip.run", "generate_payslips", [ids], {
                version_ids: versionIds,
            });
            this.notification.add("Nóminas generadas correctamente", { type: "success" });
            const action = await this.orm.call("hr.payslip.run", "action_open_payslips", [ids]);
            await this.actionService.doAction(action);
        } catch (e) {
            this.notification.add(
                e?.message || e?.data?.message || "Error al generar nóminas",
                { type: "danger" }
            );
        } finally {
            this.state.generating = false;
        }
    };

    buildRawRecord() {
        const c = this.state.config;
        const raw = {
            date_start: c.date_start,
            date_end: c.date_end,
            structure_id: c.structure_id,
            company_id: c.company_id,
            schedule_pay: c.schedule_pay,
        };
        if (c.schedule_pay === "bi-weekly" && c.payroll_period_id) {
            raw.payroll_period_id = c.payroll_period_id;
        }
        return raw;
    }

    get selectedCount() {
        return Object.values(this.state.selectedIds).filter(Boolean).length;
    }

    get structureName() {
        return ""; // Will be passed from config
    }

    get companyName() {
        return ""; // Will be passed from config
    }
}

registry.category("actions").add("l10n_hn_payroll_generation_wizard", PayrollGenerationWizard);
