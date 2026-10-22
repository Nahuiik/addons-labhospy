/** @odoo-module **/

import { Component } from "@odoo/owl";

export class StepEmployees extends Component {
    static template = "l10n_hn_hr_payroll.StepEmployees";
    static props = {
        versions: Array,
        selectedIds: Object,
        searchQuery: { type: String, optional: true },
        onToggle: Function,
        onToggleAll: Function,
        onSearchChange: Function,
    };

    get filteredVersions() {
        const q = (this.props.searchQuery || "").toLowerCase().trim();
        if (!q) return this.props.versions;
        return this.props.versions.filter(v => {
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

    get allSelected() {
        const filtered = this.filteredVersions;
        if (!filtered.length) return false;
        return filtered.every(v => this.props.selectedIds[v.id]);
    }

    get someSelected() {
        return this.filteredVersions.some(v => this.props.selectedIds[v.id]);
    }

    formatWage(version) {
        const wage = version.wage;
        const currency = version.currency_id;
        const symbol = Array.isArray(currency) ? "" : (currency && currency[1]) || "";
        if (typeof wage !== "number") return "-";
        return `${wage.toLocaleString()} ${symbol}`.trim();
    }

    getEmployeeName(version) {
        const emp = version.employee_id;
        return Array.isArray(emp) ? emp[1] : (emp && emp.display_name) || "-";
    }

    getDepartmentName(version) {
        const dept = version.department_id;
        return Array.isArray(dept) ? dept[1] : (dept && dept.display_name) || "-";
    }

    getJobName(version) {
        const job = version.job_id;
        return Array.isArray(job) ? job[1] : (job && job.display_name) || "-";
    }
}
