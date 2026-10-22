# -*- coding: utf-8 -*-
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, api, fields, _
from datetime import datetime
import io
import base64

class payrollReportXlsx(models.AbstractModel):
    _name = 'report.l10n_hn_hr_recruitment.payroll_report_xls_diseases.xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Description'

    def generate_xlsx_report(self, workbook, data, lines):
        info = self.get_data(data.get('date_from'), data.get('date_to') )  
        cont = 1
        sheet = workbook.add_worksheet(_('Enfermedades'))
        cont+=1
        format1 = workbook.add_format({'font_size': 13, 'bottom': False, 'right': False, 'left': False, 'top': False, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#000000'})
        format22 = workbook.add_format({'font_size': 12, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet.set_column(0, 0, 35) 
        sheet.set_column(1, 1, 40) 
        sheet.set_column(2, 2, 35) 
        sheet.set_column(3, 3, 20) 
        sheet.set_column(4, 4, 30) 
        sheet.set_column(5, 5, 35) 
        sheet.set_column(6, 6, 20) 
        sheet.set_column(7, 7, 35) 
        sheet.set_column(8, 8, 35) 

        company_id = self.env.user.company_id
        address = ''
        phone_email = ''
        if company_id.street and company_id.street2:
            address = company_id.street + ',' + company_id.street2
        elif company_id.street and not company_id.street2:
            address = company_id.street
        elif not company_id.street and company_id.street2:
            address = company_id.street2

        if company_id.email and company_id.phone:
            phone_email = company_id.phone + ', ' + company_id.email
        elif company_id.email and not company_id.phone:
            phone_email = company_id.email
        elif not company_id.email and company_id.phone:
            phone_email = company_id.phone

        sheet.merge_range('A2:I2', company_id.name or '', format11)
        sheet.merge_range('A3:I3', address, format1)
        sheet.merge_range('A4:I4', phone_email, format1)
        company_logo = company_id.logo
        if company_logo:
            buf_image = io.BytesIO(base64.b64decode(company_logo))
            sheet.insert_image('B1', "company_logo.png", {'image_data': buf_image, 'x_scale': 0.15, 'y_scale': 0.15})
        
        row = 6
        sheet.write(row, 0, _('Nombre del empleado'), format21)
        sheet.write(row, 1, _('Departamento'), format21)
        sheet.write(row, 2, _('Puesto'), format21)
        sheet.write(row, 3, _('DNI'), format21)
        sheet.write(row, 4, _('Proyecto'), format21)
        sheet.write(row, 5, _('Enfermedad'), format21)
        sheet.write(row, 6, _('Fecha'), format21)
        sheet.write(row, 7, _('Proceso de reclamo'), format21)
        sheet.write(row, 8, _('Observaciones'), format21)
        row +=1
        for record in info:
            sheet.write(row, 0, record['employee'], format22)
            sheet.write(row, 1, record['depto_employee'], format22)
            sheet.write(row, 2, record['job_employee'], format22)
            sheet.write(row, 3, record['dni_employee'], format22)
            sheet.write(row, 4, record['asignacion_employee'], format22)
            sheet.write(row, 5, record['disease'], format22)
            sheet.write(row, 6, record['date'], format22)
            sheet.write(row, 7, record['claim'], format22)
            sheet.write(row, 8, record['observation'], format22)
            row += 1



    def get_data(self, date_from, date_to):
        records = self.env['l10n_hn_hr_recruitment.docs_diseases'].search([
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ], order="date asc")

        info = []
        for rec in records:
            employee = rec.employee_id
            asignacion_employee = ''
            if employee and 'asignacion_id' in employee._fields:
                asignacion = employee.asignacion_id
                if asignacion:
                    asignacion_employee = (
                        getattr(asignacion, 'asignacion', None)
                        or asignacion.display_name
                        or ''
                    )
            info.append({
                'employee': rec.employee_id.name or '',
                'depto_employee': rec.employee_id.department_id.name or '',
                'job_employee': rec.employee_id.job_title or '',
                'dni_employee': rec.employee_id.identification_id or '',
                'asignacion_employee': asignacion_employee,
                'disease': rec.diseases_id.name or '',
                'claim': rec.claim or '',
                'observation': rec.observation or '',
                'date': self.change_format(rec.date) if rec.date else '',
            })
        return info


    def change_format(self, report_date):
        if not report_date:
            return ''
        return report_date.strftime('%d/%m/%Y')
