# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import base64
import csv
import io
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class VecinalIncomeImportWizard(models.TransientModel):
    """Wizard to import employee income records from CSV"""
    _name = 'l10n.hn.vecinal.income_import_wizard'
    _description = 'Import Employee Income Records from CSV'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    year_base = fields.Integer(string='Base Year', required=True,
                              default=lambda self: fields.Date.today().year - 1,
                              help='Year of the income (e.g., 2025 if applying in 2026)')
    file = fields.Binary(string='CSV File', required=True,
                        help='CSV file with columns: Employee Code/ID, Annual Income')
    filename = fields.Char(string='Filename')
    import_preview = fields.Html(string='Import Preview', readonly=True)
    
    # CSV format options
    has_header = fields.Boolean(string='File has header row', default=True)
    delimiter = fields.Char(string='Delimiter', default=',', required=True,
                           help='CSV delimiter (usually comma "," or semicolon ";")')
    
    # Column mapping
    employee_column = fields.Integer(string='Employee Column (1-based)', default=1, required=True,
                                    help='Column number containing employee code/ID (starting from 1)')
    income_column = fields.Integer(string='Income Column (1-based)', default=2, required=True,
                                  help='Column number containing annual income (starting from 1)')
    
    @api.onchange('file', 'has_header', 'delimiter', 'employee_column', 'income_column')
    def _onchange_file(self):
        """Preview CSV file content"""
        if not self.file:
            self.import_preview = False
            return
        
        try:
            file_content = base64.b64decode(self.file).decode('utf-8-sig')
            csv_reader = csv.reader(io.StringIO(file_content), delimiter=self.delimiter)
            rows = list(csv_reader)
            
            if not rows:
                self.import_preview = '<p>File is empty.</p>'
                return
            
            # Build preview table
            preview_html = '<table class="table table-bordered"><thead><tr>'
            preview_html += '<th>Row</th>'
            for i in range(len(rows[0])):
                preview_html += f'<th>Column {i+1}</th>'
            preview_html += '</tr></thead><tbody>'
            
            # Show first 10 rows
            start_row = 1 if self.has_header else 0
            for idx, row in enumerate(rows[start_row:start_row+10], start=start_row+1):
                preview_html += '<tr>'
                preview_html += f'<td>{idx}</td>'
                for cell in row:
                    preview_html += f'<td>{cell}</td>'
                preview_html += '</tr>'
            
            if len(rows) > start_row + 10:
                preview_html += f'<tr><td colspan="{len(rows[0])+1}">... and {len(rows) - start_row - 10} more rows</td></tr>'
            
            preview_html += '</tbody></table>'
            
            # Show mapping info
            preview_html += f'<p><strong>Mapping:</strong></p>'
            preview_html += f'<ul>'
            preview_html += f'<li>Employee: Column {self.employee_column}</li>'
            preview_html += f'<li>Annual Income: Column {self.income_column}</li>'
            preview_html += f'</ul>'
            
            self.import_preview = preview_html
            
        except Exception as e:
            self.import_preview = f'<p class="text-danger">Error reading file: {str(e)}</p>'
    
    def action_import(self):
        """Import income records from CSV"""
        self.ensure_one()
        
        if not self.file:
            raise ValidationError(_('Please select a CSV file to import.'))
        
        try:
            file_content = base64.b64decode(self.file).decode('utf-8-sig')
            csv_reader = csv.reader(io.StringIO(file_content), delimiter=self.delimiter)
            rows = list(csv_reader)
            
            if not rows:
                raise ValidationError(_('CSV file is empty.'))
            
            # Skip header if present
            start_row = 1 if self.has_header else 0
            data_rows = rows[start_row:]
            
            if not data_rows:
                raise ValidationError(_('No data rows found in CSV file.'))
            
            # Validate column numbers
            max_cols = max(len(row) for row in data_rows) if data_rows else 0
            if self.employee_column < 1 or self.employee_column > max_cols:
                raise ValidationError(_('Employee column number is out of range. File has %d columns.') % max_cols)
            if self.income_column < 1 or self.income_column > max_cols:
                raise ValidationError(_('Income column number is out of range. File has %d columns.') % max_cols)
            
            # Import data
            income_obj = self.env['l10n.hn.vecinal.employee_income']
            created_count = 0
            updated_count = 0
            error_count = 0
            errors = []
            
            for row_idx, row in enumerate(data_rows, start=start_row+1):
                try:
                    # Get employee identifier (code or ID)
                    employee_identifier = row[self.employee_column - 1].strip() if len(row) > self.employee_column - 1 else ''
                    income_str = row[self.income_column - 1].strip() if len(row) > self.income_column - 1 else '0'
                    
                    if not employee_identifier:
                        errors.append(f'Row {row_idx}: Empty employee identifier')
                        error_count += 1
                        continue
                    
                    # Try to parse income
                    try:
                        # Remove currency symbols and spaces
                        income_str = income_str.replace('L', '').replace('$', '').replace(',', '').replace(' ', '')
                        annual_income = float(income_str)
                    except ValueError:
                        errors.append(f'Row {row_idx}: Invalid income value "{row[self.income_column - 1]}"')
                        error_count += 1
                        continue
                    
                    # Find employee by code or ID
                    employee = self.env['hr.employee'].search([
                        ('company_id', '=', self.company_id.id),
                        '|',
                        ('barcode', '=', employee_identifier),
                        ('id', '=', int(employee_identifier) if employee_identifier.isdigit() else -1)
                    ], limit=1)
                    
                    if not employee:
                        # Try by name
                        employee = self.env['hr.employee'].search([
                            ('company_id', '=', self.company_id.id),
                            ('name', 'ilike', employee_identifier)
                        ], limit=1)
                    
                    if not employee:
                        errors.append(f'Row {row_idx}: Employee not found "{employee_identifier}"')
                        error_count += 1
                        continue
                    
                    # Check if record exists
                    existing = income_obj.search([
                        ('employee_id', '=', employee.id),
                        ('year_base', '=', self.year_base),
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)
                    
                    if existing:
                        # Update existing record
                        existing.write({
                            'annual_income': annual_income,
                            'state': 'draft'  # Reset to draft for review
                        })
                        updated_count += 1
                    else:
                        # Create new record
                        income_obj.create({
                            'employee_id': employee.id,
                            'year_base': self.year_base,
                            'company_id': self.company_id.id,
                            'annual_income': annual_income,
                            'state': 'draft'
                        })
                        created_count += 1
                
                except Exception as e:
                    errors.append(f'Row {row_idx}: {str(e)}')
                    error_count += 1
            
            # Build result message
            message_parts = []
            if created_count > 0:
                message_parts.append(_('%d records created') % created_count)
            if updated_count > 0:
                message_parts.append(_('%d records updated') % updated_count)
            if error_count > 0:
                message_parts.append(_('%d errors') % error_count)
            
            message = ', '.join(message_parts) if message_parts else _('No records processed')
            
            if errors:
                error_details = '\n'.join(errors[:10])  # Show first 10 errors
                if len(errors) > 10:
                    error_details += f'\n... and {len(errors) - 10} more errors'
                message += f'\n\nErrors:\n{error_details}'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Completed'),
                    'message': message,
                    'type': 'success' if error_count == 0 else 'warning',
                    'sticky': error_count > 0,
                }
            }
        
        except Exception as e:
            raise UserError(_('Error importing CSV file: %s') % str(e))
    
    def action_download_template(self):
        """Download CSV template file"""
        self.ensure_one()
        
        # Get active employees for the company
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=100)  # Limit to 100 for template
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output, delimiter=self.delimiter)
        
        # Header
        writer.writerow(['Employee Code/ID', 'Annual Income'])
        
        # Sample data
        for employee in employees[:10]:  # Show first 10 as example
            writer.writerow([
                employee.barcode or str(employee.id),
                0.00
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'vecinal_income_template_{self.year_base}.csv',
            'type': 'binary',
            'datas': base64.b64encode(csv_content.encode('utf-8-sig')),
            'mimetype': 'text/csv',
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
