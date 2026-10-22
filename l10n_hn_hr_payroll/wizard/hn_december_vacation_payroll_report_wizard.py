# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

import base64
from calendar import monthrange
from datetime import date
from io import BytesIO

from odoo import _, fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

_MONTH_ES = (
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
)


class HnDecemberVacationPayrollReportWizard(models.TransientModel):
    _name = 'hn.december.vacation.payroll.report.wizard'
    _description = 'Reporte Excel nómina vacaciones cierre diciembre (HN)'

    year = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: date.today().year,
    )
    company_ids = fields.Many2many(
        'res.company',
        'hn_dec_vac_payroll_wizard_company_rel',
        'wizard_id', 'company_id',
        string='Compañías',
        help='Vacío = compañías permitidas para el usuario actual.',
    )
    department_ids = fields.Many2many(
        'hr.department',
        'hn_dec_vac_payroll_wizard_department_rel',
        'wizard_id', 'department_id',
        string='Departamentos',
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        'hn_dec_vac_payroll_wizard_employee_rel',
        'wizard_id', 'employee_id',
        string='Empleados',
    )

    def _year_bounds(self):
        self.ensure_one()
        y = int(self.year)
        if y < 2000 or y > 2100:
            raise UserError(_('Indique un año válido.'))
        start = date(y, 1, 1)
        end = date(y, 12, monthrange(y, 12)[1])
        return start, end

    def _iter_report_employees(self):
        """Mismos criterios que el lote de nómina vacaciones HN cierre diciembre (versiones + saldo > 0)."""
        self.ensure_one()
        year_start, year_end = self._year_bounds()
        Run = self.env['hr.payslip.run']
        companies = self.company_ids
        if not companies:
            companies = self.env.companies
        emp_ids = self.employee_ids.ids or None
        seen = self.env['hr.employee']
        for company in companies:
            versions = Run._hn_vacation_payroll_valid_version_ids(
                year_start,
                year_end,
                company.id,
                emp_ids,
                'year_end_december',
            )
            seen |= versions.employee_id
        if self.department_ids:
            seen = seen.filtered(lambda e: e.department_id in self.department_ids)
        return seen

    def _headers(self, year):
        ys = str(year)
        return [
            _('No.'),
            _('Empleado'),
            _('Fecha de ingreso'),
            _('Mes'),
            _('Fin de año'),
            _('Días de antigüedad'),
            _('Salario para vacaciones'),
            _('Promedio diario'),
            _('Días trabajados %(y)s') % {'y': ys},
            _('Días devengados'),
            _('Pago vacaciones %(y)s') % {'y': ys},
        ]

    def _write_help_sheet(self, workbook, year, data_sheet_title):
        """Segunda hoja del libro: metodología y fórmulas (referencia para auditoría)."""
        sheet = workbook.add_worksheet(_('Ayuda'))
        sheet.set_column(0, 0, 22)
        sheet.set_column(1, 1, 88)
        title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'valign': 'vcenter'})
        sec_fmt = workbook.add_format({'bold': True, 'font_size': 11, 'valign': 'top', 'bg_color': '#E7EEF7'})
        body_fmt = workbook.add_format({'text_wrap': True, 'valign': 'top', 'font_size': 10})
        mono_fmt = workbook.add_format({
            'text_wrap': True, 'valign': 'top', 'font_size': 10, 'font_name': 'Consolas',
        })

        sections = [
            (
                _('1. Propósito'),
                _(
                    'Esta exportación respalda el cierre de vacaciones Honduras al 31 de diciembre de %(year)s. '
                    'La primera hoja («%(sheet)s») es una tabla de Excel (estilo y fila de totales automática) con '
                    'los mismos empleados elegibles que el lote «Vacaciones HN — Cierre anual» (saldo a liquidar en '
                    'nómina positivo). Las columnas «Días devengados» y «Pago vacaciones» usan el devengado teórico al '
                    'cierre y el promedio diario; véase la sección 6.'
                ) % {'year': year, 'sheet': data_sheet_title},
            ),
            (
                _('2. Salario para vacaciones (promedio 6 meses)'),
                _(
                    'Para cada empleado se toman los seis meses calendario completos anteriores al mes que contiene la '
                    'fecha de referencia (31 de diciembre de %(year)s).\n'
                    'Por cada mes, si hay línea en el Historial salarial mensual HN, el monto del mes es '
                    'salario neto del historial más comisiones del mismo mes (amount_net + amount_commission). '
                    'Si no hay registro en ese mes, se usa la remuneración mensual equivalente del contrato '
                    '(versión) al último día de ese mes (sin desglose de comisión en ese respaldo).\n'
                    'La columna «Salario para vacaciones» es el promedio aritmético de hasta seis de esos montos.'
                ) % {'year': year},
            ),
            (
                _('3. Promedio diario'),
                _(
                    'La columna «Promedio diario» usa la misma fórmula que la regla salarial HN_VAC_PAY en la '
                    'estructura de vacaciones HN:\n\n'
                    'Promedio diario = Salario para vacaciones × (14 ÷ 12) ÷ 30\n\n'
                    'Equivale a dividir el salario mensual promedio de la columna anterior entre (360 ÷ 14) '
                    '(aprox. 25,714). El factor 14/12 refleja la proporción de vacaciones sobre la base mensual '
                    'en el marco HN implementado en este módulo y la nómina.'
                ),
            ),
            (
                _('4. Días de antigüedad (hasta fin de año)'),
                _(
                    'Cuenta días naturales desde la fecha de ingreso del contrato hasta el 31 de diciembre '
                    'de %(year)s inclusive. Si el empleado tiene fecha de salida dentro de ese lapso, el cómputo '
                    'termina ese día (inclusive).'
                ) % {'year': year},
            ),
            (
                _('5. Días trabajados en el año %s') % year,
                _(
                    'Días naturales entre el 1 de enero y el 31 de diciembre de %(year)s, recortados por la '
                    'fecha de ingreso (no se cuenta antes del ingreso) y, si existe, por la fecha de salida en ese '
                    'año. Es un dato contextual (calendario civil), no siempre idéntico a «días laborables» de un '
                    'reporte interno distinto.'
                ) % {'year': year},
            ),
            (
                _('6. Días devengados (al 31 de diciembre)'),
                _(
                    'La columna refleja los días de vacaciones devengados en teoría a la fecha de cierre '
                    '(31 de diciembre de %(year)s), según el plan de vacaciones HN del empleado:\n'
                    '• Si ya tiene al menos un año de antigüedad a esa fecha: días del plan para la tabla de '
                    'antigüedad (mismo criterio que «días que le corresponden» con antigüedad medida al cierre).\n'
                    '• Si tiene menos de un año y el plan permite acumulación mensual proporcional: '
                    '(meses completos desde el ingreso hasta el cierre ÷ 12) × días del primer año del plan, '
                    'redondeo a un decimal; menos de un mes completado: 0.\n'
                    '• Sin plan o sin proporcional mensual antes del primer aniversario: 0.\n\n'
                    'No es el saldo de asignaciones ni los días pendientes de liquidar en nómina (FIFO); sirve para '
                    'empatar con planillas de vacaciones devengadas en el año.'
                ) % {'year': year},
            ),
            (
                _('7. Pago vacaciones %s') % year,
                _(
                    'Importe informativo: Pago vacaciones = Días devengados × Promedio diario. '
                    'La liquidación en Odoo con la regla HN_VAC_PAY sigue usando los días y reglas del lote de '
                    'nómina de vacaciones; compare importes con RRHH si difieren de esta planilla.'
                ),
            ),
            (
                _('8. Quién entra en el listado'),
                _(
                    'Los mismos empleados que puede incluir el lote «Vacaciones HN — Cierre anual»: versión de '
                    'contrato válida en el período, saldo a liquidar en nómina de vacaciones (asignaciones HN) '
                    'mayor que cero, y reglas del cierre (p. ej. no ingreso en diciembre del año). La columna '
                    '«Días devengados» del Excel muestra el devengado teórico al 31-dic, no ese saldo de liquidación. '
                    'Los filtros del asistente recortan el universo.'
                ),
            ),
        ]

        sheet.merge_range(0, 0, 0, 1, _('Ayuda — Cálculos y criterios (cierre diciembre %s)') % year, title_fmt)
        sheet.write(1, 0, _('Tema'), sec_fmt)
        sheet.write(1, 1, _('Descripción'), sec_fmt)
        row = 2
        for tema, descripcion in sections:
            sheet.write(row, 0, tema, sec_fmt)
            sheet.write(row, 1, descripcion, body_fmt)
            lines = descripcion.count('\n') + 1
            sheet.set_row(row, min(220, 12 + lines * 14))
            row += 1

        sheet.merge_range(row + 1, 0, row + 1, 1, _('Fórmulas resumidas (referencia rápida)'), sec_fmt)
        formulas = (
            'promedio_mensual = media( 6 meses: neto + comision por mes en historial HN; si no hay línea, sueldo version )\n'
            'promedio_diario = promedio_mensual * (14/12) / 30\n'
            'dias_devengados = devengado teorico al 31-dic (plan HN; proporcional si < 1 año)\n'
            'pago_vacaciones = promedio_diario * dias_devengados'
        )
        sheet.merge_range(row + 2, 0, row + 2, 1, formulas, mono_fmt)
        sheet.set_row(row + 2, 90)

    def action_generate_excel(self):
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_('La biblioteca xlsxwriter no está instalada. Contacte al administrador.'))
        year_start, year_end = self._year_bounds()
        year = year_start.year
        employees = self._iter_report_employees()
        if not employees:
            raise UserError(
                _('No hay empleados con saldo a liquidar en vacaciones HN para el cierre de diciembre %(y)s '
                  'con los filtros actuales.') % {'y': year}
            )
        employees = employees.sorted(key=lambda e: (e.name or '').casefold())

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        header_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': '#FFFFFF',
            'border': 1,
            'valign': 'vcenter',
        })
        cell_fmt = workbook.add_format({'border': 1})
        date_fmt = workbook.add_format({'border': 1, 'num_format': 'dd-mmm-yy'})
        money_fmt = workbook.add_format({'border': 1, 'num_format': '"L" #,##0.00'})
        int_fmt = workbook.add_format({'border': 1, 'num_format': '0'})
        decimal_fmt = workbook.add_format({'border': 1, 'num_format': '0.00'})

        data_sheet_title = _('Nómina vacaciones')
        sheet = workbook.add_worksheet(data_sheet_title)
        headers = self._headers(year)
        last_col = len(headers) - 1

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 28)
        sheet.set_column(2, 5, 12)
        sheet.set_column(6, 7, 14)
        sheet.set_column(8, last_col, 14)

        table_columns = []
        for col_idx, h in enumerate(headers):
            coldef = {'header': h, 'header_format': header_fmt}
            if col_idx == 0:
                coldef['total_string'] = _('Totales')
            elif col_idx in (8, 9, 10):
                coldef['total_function'] = 'sum'
            if col_idx == 0:
                coldef['format'] = int_fmt
            elif col_idx in (2, 4):
                coldef['format'] = date_fmt
            elif col_idx in (6, 7, 10):
                coldef['format'] = money_fmt
            elif col_idx in (5, 8):
                coldef['format'] = int_fmt
            elif col_idx == 9:
                coldef['format'] = decimal_fmt
            else:
                coldef['format'] = cell_fmt
            table_columns.append(coldef)

        row = 1
        for num, emp in enumerate(employees, start=1):
            hire = emp.contract_date_start
            mes = _MONTH_ES[hire.month - 1] if hire else ''
            prom = emp._hn_vacation_payroll_salary_average_6m_plus_commission(year_end)
            daily = (prom * 14.0 / 12.0) / 30.0 if prom else 0.0
            tenure_days = emp._hn_vacation_tenure_calendar_days_end(year_end)
            worked = emp._hn_vacation_calendar_days_worked_year(year)
            devengados = emp._hn_vacation_devengados_at(year_end)
            pay_vac = daily * devengados if daily and devengados else 0.0

            sheet.write(row, 0, num, int_fmt)
            sheet.write(row, 1, emp.name or '', cell_fmt)
            sheet.write(row, 2, hire or '', date_fmt if hire else cell_fmt)
            sheet.write(row, 3, mes, cell_fmt)
            sheet.write(row, 4, year_end, date_fmt)
            sheet.write(row, 5, tenure_days, int_fmt)
            sheet.write(row, 6, prom, money_fmt)
            sheet.write(row, 7, daily, money_fmt)
            sheet.write(row, 8, worked, int_fmt)
            sheet.write(row, 9, devengados, decimal_fmt)
            sheet.write(row, 10, pay_vac, money_fmt)
            row += 1

        n = len(employees)
        if n:
            sheet.add_table(
                0, 0, n + 1, last_col,
                {
                    'total_row': True,
                    'name': 'NominaVacacionesHN',
                    'style': 'Table Style Medium 9',
                    'columns': table_columns,
                },
            )

        self._write_help_sheet(workbook, year, data_sheet_title)
        workbook.close()
        output.seek(0)
        filename = _('Nomina_Vacaciones_Diciembre_%(y)s.xlsx') % {'y': year}
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(output.read()),
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true&filename={filename}',
            'target': 'self',
        }
