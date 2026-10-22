# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import base64
import io
import os
import re
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
try:
    import openpyxl
except ImportError:
    openpyxl = None


class HrEmployeeImportWizard(models.TransientModel):
    """Wizard for importing employees from Excel template"""
    _name = 'hr.employee.import.wizard'
    _description = 'Employee Import Wizard'

    name = fields.Char(string='Name', default='Employee Import')
    excel_file = fields.Binary(string='Excel File', required=False)
    excel_filename = fields.Char(string='Filename')
    example_file = fields.Binary(string='Example File', readonly=True)
    example_filename = fields.Char(string='Example Filename', default='ejemplo_importacion_empleados.xlsx', readonly=True)
    import_mode = fields.Selection([
        ('create', 'Create Only'),
        ('update', 'Update Only'),
        ('mixed', 'Create or Update'),
    ], string='Import Mode', required=True, default='mixed',
       help='Create: Only creates new employees\nUpdate: Only updates existing employees\nMixed: Creates new and updates existing')
    
    create_departments = fields.Boolean(string='Create Departments', default=True,
                                        help='Create departments if they do not exist')
    create_jobs = fields.Boolean(string='Create Jobs', default=True,
                                  help='Create jobs if they do not exist')
    create_banks = fields.Boolean(string='Create Banks', default=True,
                                   help='Create banks if they do not exist')
    create_contracts = fields.Boolean(string='Create Contracts', default=True,
                                       help='Create initial contracts for employees')
    
    # Results
    import_log = fields.Html(string='Import Log', readonly=True)
    error_log = fields.Html(string='Error Log', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('imported', 'Imported'),
    ], string='State', default='draft')
    
    def action_download_example(self):
        """Download example Excel file"""
        self.ensure_one()
        
        # Get the path to the example file
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        example_path = os.path.join(module_path, 'static', 'description', 'ejemplo_importacion_empleados.xlsx')
        
        if not os.path.exists(example_path):
            raise UserError(_('Example file not found at: %s') % example_path)
        
        # Read file and encode to base64
        with open(example_path, 'rb') as f:
            file_data = base64.b64encode(f.read())
        
        # Create a temporary attachment to download
        attachment = self.env['ir.attachment'].create({
            'name': 'ejemplo_importacion_empleados.xlsx',
            'type': 'binary',
            'datas': file_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        
        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
    
    @api.model
    def default_get(self, fields_list):
        """Preload example file when creating wizard"""
        res = super().default_get(fields_list)
        
        # Load example file
        try:
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            example_path = os.path.join(module_path, 'static', 'description', 'ejemplo_importacion_empleados.xlsx')
            
            if os.path.exists(example_path):
                with open(example_path, 'rb') as f:
                    res['example_file'] = base64.b64encode(f.read())
        except Exception:
            pass
        
        return res
    
    def action_import(self):
        """Import employees from Excel file"""
        self.ensure_one()
        
        if not openpyxl:
            raise UserError(_('Please install openpyxl library: pip install openpyxl'))
        
        if not self.excel_file:
            raise ValidationError(_('Please select an Excel file to import.'))
        
        # Decode file
        try:
            file_data = base64.b64decode(self.excel_file)
            # Create a BytesIO object from the decoded data
            excel_file = io.BytesIO(file_data)
            workbook = openpyxl.load_workbook(filename=excel_file, data_only=True)
        except Exception as e:
            raise UserError(_('Error reading Excel file: %s') % str(e))
        
        # Get worksheet - search case-insensitive
        worksheet = None
        for sheet_name in workbook.sheetnames:
            if sheet_name.lower() == 'datos':
                worksheet = workbook[sheet_name]
                break
        
        if not worksheet:
            raise UserError(_('Worksheet "datos" (case-insensitive) not found in Excel file. Available sheets: %s') % ', '.join(workbook.sheetnames))
        
        # Expected columns (based on SOW document)
        expected_columns = [
            'Nombre completo del empleado',
            'Municipio',
            'Colonia',
            'Punto de referencia',
            'Identidad',
            'Fecha de nacimiento',
            'Teléfono privado',
            'Correo electronico privado',
            'Departamento',
            'Puesto de trabajo',
            'Jefe inmediato',
            'Teléfono celular laboral',
            'Fecha de Ingreso',
            'Salario Mensual',
            'Nombre Contacto de Emergencia',
            'Relación con Contacto Emergencia',
            'Teléfono Contacto Emergencia',
            'Cuenta bancaria',
            'Banco',
            'Genero',
        ]
        
        # Read headers
        headers = []
        header_row = None
        for idx, row in enumerate(worksheet.iter_rows(min_row=1, max_row=10, values_only=True)):
            if row[0] and 'Nombre completo' in str(row[0]):
                header_row = idx + 1
                headers = [str(cell).strip() if cell else '' for cell in row]
                break
        
        if not headers:
            raise UserError(_('Could not find header row in Excel file.'))
        
        # Validate headers
        missing_headers = []
        for expected in expected_columns[:5]:  # Required headers
            if expected not in headers:
                missing_headers.append(expected)
        
        if missing_headers:
            raise UserError(_('Missing required columns: %s') % ', '.join(missing_headers))
        
        # Process rows
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        log_messages = []
        
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 2):
            if not row[0]:  # Skip empty rows
                continue
            
            try:
                # Map values
                values = {}
                for idx, header in enumerate(headers):
                    if idx < len(row):
                        values[header] = row[idx]
                
                # Validate required fields
                identification = str(values.get('Identidad', '')).strip()
                if not identification:
                    errors.append({
                        'row': row_idx,
                        'field': 'Identidad',
                        'value': '',
                        'error': _('Identification is required'),
                    })
                    error_count += 1
                    continue
                
                # Validate identification format (13 digits)
                identification = re.sub(r'[^0-9]', '', identification)
                if len(identification) != 13:
                    errors.append({
                        'row': row_idx,
                        'field': 'Identidad',
                        'value': values.get('Identidad', ''),
                        'error': _('Identification must be 13 digits'),
                    })
                    error_count += 1
                    continue
                
                # Find or create employee
                employee = self.env['hr.employee'].search([
                    ('identification_id', '=', identification)
                ], limit=1)
                
                employee_name = str(values.get('Nombre completo del empleado', '')).strip().upper()
                if not employee_name:
                    errors.append({
                        'row': row_idx,
                        'field': 'Nombre completo del empleado',
                        'value': '',
                        'error': _('Employee name is required'),
                    })
                    error_count += 1
                    continue
                
                if employee:
                    if self.import_mode == 'create':
                        errors.append({
                            'row': row_idx,
                            'field': 'Identidad',
                            'value': identification,
                            'error': _('Employee already exists (Create mode)'),
                        })
                        error_count += 1
                        continue
                    
                    # Update employee
                    self._update_employee(employee, values, row_idx, errors)
                    updated_count += 1
                    log_messages.append(_('Row %d: Updated employee %s') % (row_idx, employee_name))
                else:
                    if self.import_mode == 'update':
                        errors.append({
                            'row': row_idx,
                            'field': 'Identidad',
                            'value': identification,
                            'error': _('Employee not found (Update mode)'),
                        })
                        error_count += 1
                        continue
                    
                    # Create employee
                    employee = self._create_employee(values, row_idx, errors)
                    if employee:
                        created_count += 1
                        log_messages.append(_('Row %d: Created employee %s') % (row_idx, employee_name))
                    else:
                        error_count += 1
                        
            except Exception as e:
                errors.append({
                    'row': row_idx,
                    'field': 'General',
                    'value': '',
                    'error': str(e),
                })
                error_count += 1
        
        # Generate logs
        log_html = '<ul>'
        for msg in log_messages[:100]:  # Limit to 100 messages
            log_html += f'<li>{msg}</li>'
        log_html += '</ul>'
        log_html += f'<p><strong>Summary:</strong> Created: {created_count}, Updated: {updated_count}, Errors: {error_count}</p>'
        
        error_html = '<table border="1"><tr><th>Row</th><th>Field</th><th>Value</th><th>Error</th></tr>'
        for error in errors[:100]:  # Limit to 100 errors
            error_html += f'<tr><td>{error["row"]}</td><td>{error["field"]}</td><td>{error["value"]}</td><td>{error["error"]}</td></tr>'
        error_html += '</table>'
        
        self.write({
            'import_log': log_html,
            'error_log': error_html if errors else '<p>No errors</p>',
            'state': 'imported',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Results'),
            'res_model': 'hr.employee.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def _create_employee(self, values, row_idx, errors):
        """Create new employee from values"""
        try:
            # Parse date fields
            birthday = self._parse_date(values.get('Fecha de nacimiento', ''))
            date_start = self._parse_date(values.get('Fecha de Ingreso', ''))
            
            if not date_start and self.create_contracts:
                errors.append({
                    'row': row_idx,
                    'field': 'Fecha de Ingreso',
                    'value': values.get('Fecha de Ingreso', ''),
                    'error': _('Start date is required for contract creation'),
                })
                return False
            
            # Get or create department
            department_id = False
            dept_name = str(values.get('Departamento', '')).strip()
            if dept_name and self.create_departments:
                department = self.env['hr.department'].search([('name', '=', dept_name)], limit=1)
                if not department:
                    department = self.env['hr.department'].create({'name': dept_name})
                department_id = department.id
            
            # Get or create job
            job_id = False
            job_name = str(values.get('Puesto de trabajo', '')).strip()
            if job_name and self.create_jobs:
                job = self.env['hr.job'].search([('name', '=', job_name)], limit=1)
                if not job:
                    job = self.env['hr.job'].create({'name': job_name})
                job_id = job.id
            
            # Create employee
            employee_vals = {
                'name': str(values.get('Nombre completo del empleado', '')).strip().upper(),
                'identification_id': str(values.get('Identidad', '')).strip(),
                'birthday': birthday,
                'private_phone': self._clean_phone(values.get('Teléfono privado', '')),
                'private_email': self._clean_email(values.get('Correo electronico privado', '')),
                'mobile_phone': self._clean_phone(values.get('Teléfono celular laboral', '')),
                'department_id': department_id,
                'job_id': job_id,
                'emergency_contact': str(values.get('Nombre Contacto de Emergencia', '')).strip() or False,
                'emergency_relation': str(values.get('Relación con Contacto Emergencia', '')).strip() or False,
                'emergency_phone': self._clean_phone(values.get('Teléfono Contacto Emergencia', '')),
                'sex': self._map_gender(values.get('Genero', '')),
            }
            
            employee = self.env['hr.employee'].create(employee_vals)
            
            # Create contract if requested
            if self.create_contracts and date_start:
                wage = self._parse_float(values.get('Salario Mensual', '0'))
                if wage > 0:
                    employee.create_contract_version(
                        wage=wage,
                        date_start=date_start,
                        periodicity='monthly',
                        job_id=job_id,
                        department_id=department_id,
                    )
            
            # Handle bank account
            bank_name = str(values.get('Banco', '')).strip()
            account_number = str(values.get('Cuenta bancaria', '')).strip()
            if bank_name and account_number:
                self._create_bank_account(employee, bank_name, account_number)
            
            # Handle address
            self._update_address(employee, values)
            
            return employee
            
        except Exception as e:
            errors.append({
                'row': row_idx,
                'field': 'General',
                'value': '',
                'error': _('Error creating employee: %s') % str(e),
            })
            return False
    
    def _update_employee(self, employee, values, row_idx, errors):
        """Update existing employee"""
        try:
            update_vals = {}
            
            # Update allowed fields
            if values.get('Teléfono privado'):
                update_vals['private_phone'] = self._clean_phone(values.get('Teléfono privado', ''))
            if values.get('Correo electronico privado'):
                update_vals['private_email'] = self._clean_email(values.get('Correo electronico privado', ''))
            if values.get('Teléfono celular laboral'):
                update_vals['mobile_phone'] = self._clean_phone(values.get('Teléfono celular laboral', ''))
            if values.get('Departamento'):
                dept_name = str(values.get('Departamento', '')).strip()
                if dept_name and self.create_departments:
                    department = self.env['hr.department'].search([('name', '=', dept_name)], limit=1)
                    if not department:
                        department = self.env['hr.department'].create({'name': dept_name})
                    update_vals['department_id'] = department.id
            if values.get('Puesto de trabajo'):
                job_name = str(values.get('Puesto de trabajo', '')).strip()
                if job_name and self.create_jobs:
                    job = self.env['hr.job'].search([('name', '=', job_name)], limit=1)
                    if not job:
                        job = self.env['hr.job'].create({'name': job_name})
                    update_vals['job_id'] = job.id
            if values.get('Genero'):
                update_vals['sex'] = self._map_gender(values.get('Genero', ''))
            
            if update_vals:
                employee.write(update_vals)
            
            # Update address
            self._update_address(employee, values)
            
            # Update bank account
            bank_name = str(values.get('Banco', '')).strip()
            account_number = str(values.get('Cuenta bancaria', '')).strip()
            if bank_name and account_number:
                self._create_bank_account(employee, bank_name, account_number)
            
        except Exception as e:
            errors.append({
                'row': row_idx,
                'field': 'General',
                'value': '',
                'error': _('Error updating employee: %s') % str(e),
            })
    
    def _update_address(self, employee, values):
        """Update employee address"""
        # In Odoo 19, use work_contact_id instead of address_home_id
        if not employee.work_contact_id:
            # Create partner if needed
            partner = self.env['res.partner'].create({
                'name': employee.name,
                'is_company': False,
            })
            employee.work_contact_id = partner.id
        
        partner = employee.work_contact_id
        address_vals = {}
        
        if values.get('Municipio'):
            address_vals['city'] = str(values.get('Municipio', '')).strip()
        if values.get('Colonia'):
            address_vals['street2'] = str(values.get('Colonia', '')).strip()
        if values.get('Punto de referencia'):
            address_vals['street'] = str(values.get('Punto de referencia', '')).strip()
        
        if address_vals:
            partner.write(address_vals)
    
    def _create_bank_account(self, employee, bank_name, account_number):
        """Create or update bank account"""
        # In Odoo 19, use work_contact_id instead of address_home_id
        if not employee.work_contact_id:
            # Create partner if needed
            partner = self.env['res.partner'].create({
                'name': employee.name,
                'is_company': False,
            })
            employee.work_contact_id = partner.id
        
        company = employee.company_id or self.env.company
        bank = self.env['res.bank'].search(
            [('name', '=', bank_name), ('company_id', '=', company.id)], limit=1
        )
        if not bank and self.create_banks:
            bank = self.env['res.bank'].create({'name': bank_name, 'company_id': company.id})
        
        if bank:
            # Find or create bank account
            account = self.env['res.partner.bank'].search([
                ('partner_id', '=', employee.work_contact_id.id),
                ('acc_number', '=', account_number),
            ], limit=1)
            
            if not account:
                bank_account = self.env['res.partner.bank'].create({
                    'partner_id': employee.work_contact_id.id,
                    'bank_id': bank.id,
                    'acc_number': account_number,
                })
                # Link bank account to employee (Many2many relationship)
                employee.bank_account_ids = [(4, bank_account.id)]
    
    def _parse_date(self, value):
        """Parse date from string or datetime object"""
        if not value:
            return False
        
        # If it's already a date object, return it
        if hasattr(value, 'date'):
            return value.date()
        
        # If it's a datetime object, extract the date part
        if isinstance(value, datetime):
            return value.date()
        
        value = str(value).strip()
        if not value or value == 'None':
            return False
        
        # Try to parse datetime format first (YYYY-MM-DD HH:MM:SS)
        try:
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            return dt.date()
        except:
            pass
        
        # Try to parse datetime format without seconds (YYYY-MM-DD HH:MM)
        try:
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M')
            return dt.date()
        except:
            pass
        
        # Try different date formats
        formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y', '%m-%d-%Y']
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except:
                continue
        
        return False
    
    def _parse_float(self, value):
        """Parse float from string"""
        if not value:
            return 0.0
        
        try:
            value = str(value).replace(',', '').strip()
            return float(value)
        except:
            return 0.0
    
    def _clean_phone(self, value):
        """Clean phone number (digits only)"""
        if not value:
            return False
        return re.sub(r'[^0-9]', '', str(value))
    
    def _clean_email(self, value):
        """Clean email (lowercase, no accents)"""
        if not value:
            return False
        email = str(value).lower().strip()
        # Basic email validation
        if '@' in email and '.' in email:
            return email
        return False
    
    def _map_gender(self, value):
        """Map gender values to sex field (male/female/other)"""
        if not value:
            return False
        
        value = str(value).upper().strip()
        mapping = {
            'MASCULINO': 'male',
            'FEMENINO': 'female',
            'OTRO': 'other',
        }
        return mapping.get(value, False)
