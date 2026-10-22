/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { EmployeeReportDashboard } from "./employee_report_dashboard";
import { RegionalHrDashboard } from "./regional_dashboard";

async function hasGroupSafe(xmlId) {
    try {
        return await user.hasGroup(xmlId);
    } catch {
        return false;
    }
}

class GnHrMainDashboard extends Component {
    static template = "gn_hr_dashboard.MainDashboard";
    static components = { EmployeeReportDashboard, RegionalHrDashboard };
    static props = { ...standardActionServiceProps };

    setup() {
        this.state = useState({
            activeTab: "reports",
            showRegional: false,
            initialized: false,
        });
        onWillStart(async () => {
            const ctx = this.props.action?.context || {};
            const wantsRegional = ctx.dashboard_default_tab === "regional";
            const wantsReports = ctx.dashboard_default_tab === "reports";
            const showRegional =
                (await hasGroupSafe(
                    "gn_hr_dashboard.group_gn_hr_dashboard_regional"
                )) ||
                (await hasGroupSafe(
                    "gn_hr_intercompany.group_hr_intercompany_regional_manager"
                ));
            this.state.showRegional = showRegional;
            if (wantsRegional && showRegional) {
                this.state.activeTab = "regional";
            } else if (wantsReports) {
                this.state.activeTab = "reports";
            } else if (ctx.dashboard_default_tab === "help") {
                this.state.activeTab = "help";
            } else {
                this.state.activeTab = "reports";
            }
            this.state.initialized = true;
        });
        onMounted(() => {
            // Carácter de ancho cero: evita "Sin nombre" (Unnamed) del breadcrumb si name vacío.
            this.env.config?.setDisplayName?.("\u200b");
        });
    }

    tabReports() {
        return _t("Informes de empleados");
    }

    tabRegional() {
        return _t("Vista regional");
    }

    tabHelp() {
        return _t("Ayuda");
    }

    helpTitle() {
        return _t("Cómo se calculan los KPI (Vista regional)");
    }

    helpIntro() {
        return _t(
            "Los datos usan las compañías asignadas al usuario y el filtro de país. El período es el mes (año/mes) o el rango Desde/Hasta si ambas fechas están indicadas (el rango tiene prioridad). Las tendencias de gráficos usan el fin del período como referencia."
        );
    }

    helpKpisBlock1() {
        return _t("Primera fila de tarjetas");
    }

    helpKpiHeadcount() {
        return _t(
            "Headcount: cantidad de empleados activos en las compañías incluidas."
        );
    }

    helpKpiPayroll() {
        return _t(
            "Costo nómina: suma del campo bruto (gross) de nóminas en estado hecho/pagado cuyo período (desde/hasta de la nómina) se solapa con el período filtrado."
        );
    }

    helpKpiTurnover() {
        return _t(
            "Rotación (%): empleados dados de baja (no activos) con fecha de baja en los doce meses anteriores al fin del período, dividido entre el headcount actual y multiplicado por 100."
        );
    }

    helpKpiAbsencePct() {
        return _t(
            "Ausentismo (%): días de ausencia validados (permisos/ausencias) que cruzan el período, dividido entre headcount × 22 días de referencia y multiplicado por 100."
        );
    }

    helpKpiOvertime() {
        return _t(
            "Horas extra: suma de horas extra en incidencias de asistencia aprobadas o aplicadas, tipo horas extra, en el período (si el módulo de incidencias está instalado)."
        );
    }

    helpKpiLeaveBal() {
        return _t(
            "Vacaciones pendientes: suma de días de asignación validada menos días ya tomados, para empleados activos de las compañías filtradas."
        );
    }

    helpKpisBlock2() {
        return _t("Segunda fila de tarjetas");
    }

    helpKpiAbsenceDays() {
        return _t(
            "Días ausencia: suma de días (campo días de la ausencia) de permisos validados que intersectan el período."
        );
    }

    helpKpiLate() {
        return _t(
            "Tardanzas: número de incidencias de tipo tardanza con fecha en el período (si aplica)."
        );
    }

    helpKpiPayrollVar() {
        return _t(
            "Variación nómina vs mes anterior: compara el costo bruto del período filtrado con el del mes calendario completo anterior al mes que contiene el inicio del período. Si no hay base en el mes anterior y sí hay costo actual, no se muestra porcentaje (—)."
        );
    }

    helpKpiMovement() {
        return _t(
            "Movimiento neto: altas (fecha de inicio de contrato en el período) menos bajas (fecha de baja en el período) en las compañías filtradas."
        );
    }

    helpKpiContracts() {
        return _t(
            "Contratos por vencer: conteos de empleados activos con fin de contrato hoy o en los próximos 30, 61–60 y 61–90 días (ventanas disjuntas desde la fecha de hoy del servidor)."
        );
    }

    helpKpiTenure() {
        return _t(
            "Antigüedad media (años): media de años desde la fecha de inicio de contrato hasta hoy, solo empleados activos con inicio de contrato informado."
        );
    }

    helpKpisBlockExtra() {
        return _t("Indicadores y tablas adicionales");
    }

    helpKpiPayrollPerEmployee() {
        return _t(
            "Costo nómina por empleado: costo bruto de nómina del período dividido entre el headcount activo (mismas reglas de solape de nóminas que la tarjeta de costo total)."
        );
    }

    helpAbsenceByType() {
        return _t(
            "Ausencias por tipo (gráfico): mismos datos que el indicador de días por tipo de permiso, mostrados como barras horizontales (días por tipo)."
        );
    }

    helpDiversitySex() {
        return _t(
            "Plantilla por sexo: reparto del headcount activo agrupado por el campo sex del empleado (etiquetas según la definición del sistema)."
        );
    }

    helpRecruitment() {
        return _t(
            "Reclutamiento: número de puestos de trabajo (hr.job) activos con meta de contratación mayor que cero y suma de esas metas. Si el módulo Reclutamiento está instalado, además: candidatos contratados en el período (fecha de cierre en el intervalo) y media de días desde la solicitud hasta el cierre."
        );
    }

    helpOvertimeVariation() {
        return _t(
            "Variación de horas extra: compara la suma de horas extra del período filtrado con la del mes calendario completo anterior (misma fuente: incidencias tipo horas extra aprobadas o aplicadas). Si el mes anterior suma cero y el actual es positivo, el porcentaje no aplica (—)."
        );
    }

    helpTenureBands() {
        return _t(
            "Antigüedad por bandas (gráfico): mismas bandas y conteos que el indicador textual, en barras verticales."
        );
    }

    helpPayrollPerEmpTrendChart() {
        return _t(
            "Gráfico costo / empleado por mes: para cada uno de los seis meses hasta el fin del período, suma del bruto de nóminas con período contenido en ese mes calendario, dividida entre el headcount al último día del mes (misma regla que el headcount de fin de mes en altas/bajas). Si el headcount es cero, el punto no se muestra."
        );
    }

    helpMovementHeadcountLine() {
        return _t(
            "Gráfico altas y bajas: además de altas y bajas por mes, una línea muestra el headcount al último día de cada mes (empleados con inicio de contrato ≤ ese día y activos o con fecha de baja posterior a ese día)."
        );
    }

    helpContractTypeCharts() {
        return _t(
            "Tipo de contrato: el gráfico circular refleja empleados activos actuales agrupados por tipo de contrato. El gráfico de líneas muestra, para los doce meses hasta el fin del período, cuántos empleados encajaban en esa regla de headcount al cierre de cada mes, desglosados por el tipo de contrato actual del registro (aproximación sin histórico de versiones). Si el modelo no expone tipo de contrato en el empleado, no se muestran."
        );
    }

    helpSectionChartsAlerts() {
        return _t("Gráficos y alertas");
    }

    helpCharts() {
        return _t(
            "Gráficos generales: tras la tarjeta de costo/empleado y el bloque de reclutamiento, línea de costo nómina por empleado (seis meses); fila con ausencias por tipo, plantilla por sexo y antigüedad por bandas; headcount por compañía, tendencia de costo de nómina por compañía e incidencias; altas/bajas con headcount de fin de mes; tipo de contrato (línea y circular) cuando aplica."
        );
    }

    helpAlerts() {
        return _t(
            "Alertas: el contador de contratos refleja actividades de correo con resumen que contiene «Contrato por vencer»; incidencias pendientes son registros de incidencia en estado pendiente (si el modelo existe)."
        );
    }

    setTab(tab) {
        this.state.activeTab = tab;
    }
}

registry.category("actions").add("gn_hr_main_dashboard", GnHrMainDashboard);
