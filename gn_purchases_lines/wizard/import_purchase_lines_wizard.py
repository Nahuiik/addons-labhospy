# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

try:
    import xlrd
except ImportError:
    xlrd = None

_logger = logging.getLogger(__name__)


class ImportPurchaseLinesWizard(models.TransientModel):
    _name = 'gn_purchases_lines.import_wizard'
    _description = 'Wizard para importar líneas de orden de compra'

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Orden de Compra',
        required=True,
        readonly=True,
    )
    
    file_data = fields.Binary(
        string='Archivo',
        required=True,
        help='Archivo CSV o Excel con las líneas a importar'
    )
    
    file_name = fields.Char(
        string='Nombre del Archivo',
    )
    
    product_details_option = fields.Selection(
        selection=[
            ('product', 'Tomar detalles del producto'),
            ('file', 'Tomar detalles del archivo'),
            ('pricelist', 'Tomar detalles con lista de precios adaptada'),
        ],
        string='Opción de Detalles del Producto',
        default='product',
        required=True,
        help="""- Tomar detalles del producto: Usa UOM y precio del producto
- Tomar detalles del archivo: Usa todos los datos del archivo
- Tomar detalles con lista de precios: Usa precios de la lista de precios del proveedor"""
    )
    
    import_product_by = fields.Selection(
        selection=[
            ('code', 'Código (Referencia Interna)'),
            ('barcode', 'Código de Barras'),
            ('name', 'Nombre'),
        ],
        string='Importar Producto Por',
        default='code',
        required=True,
    )
    
    create_product_if_not_found = fields.Boolean(
        string='Crear producto si no existe',
        default=False,
        help='Si está marcado, creará productos nuevos cuando se importe por nombre'
    )

    def action_import(self):
        """Procesa el archivo e importa las líneas"""
        self.ensure_one()
        
        if not self.file_data:
            raise ValidationError(_('Debe seleccionar un archivo para importar.'))
        
        # Decodificar el archivo
        file_content = base64.b64decode(self.file_data)
        
        # Determinar tipo de archivo
        file_ext = self.file_name.split('.')[-1].lower() if self.file_name else ''
        
        if file_ext == 'csv':
            lines_data = self._parse_csv(file_content)
        elif file_ext in ['xls', 'xlsx']:
            if not xlrd:
                raise UserError(_('Por favor instale la librería xlrd: pip install xlrd'))
            lines_data = self._parse_excel(file_content, file_ext)
        else:
            raise ValidationError(_('Formato de archivo no soportado. Use CSV o Excel (.xls, .xlsx)'))
        
        if not lines_data:
            raise ValidationError(_('El archivo está vacío o no tiene datos válidos.'))
        
        # Importar las líneas
        errors = []
        created_lines = []
        
        for idx, line_data in enumerate(lines_data, start=2):  # Empezar en 2 porque la fila 1 es el encabezado
            try:
                self._create_purchase_line(line_data, idx)
                created_lines.append(idx)
            except Exception as e:
                errors.append(_('Fila %d: %s') % (idx, str(e)))
                _logger.error('Error importando línea %d: %s', idx, str(e))
        
        # Mostrar resultado
        if errors:
            error_msg = '\n'.join(errors[:10])  # Mostrar máximo 10 errores
            if len(errors) > 10:
                error_msg += '\n... y %d errores más' % (len(errors) - 10)
            raise ValidationError(_('Se encontraron errores durante la importación:\n\n%s') % error_msg)
        
        # Cerrar el wizard y mostrar notificación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Importación Exitosa'),
                'message': _('Se importaron %d líneas correctamente.') % len(created_lines),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _parse_csv(self, file_content):
        """Parsea un archivo CSV"""
        try:
            # Intentar diferentes encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            content_str = None
            
            for encoding in encodings:
                try:
                    content_str = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if not content_str:
                raise ValidationError(_('No se pudo decodificar el archivo CSV.'))
            
            csv_reader = csv.DictReader(io.StringIO(content_str))
            lines = []
            
            for row in csv_reader:
                # Limpiar espacios en blanco
                cleaned_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
                if any(cleaned_row.values()):  # Solo agregar si tiene datos
                    lines.append(cleaned_row)
            
            return lines
        except Exception as e:
            raise ValidationError(_('Error al leer el archivo CSV: %s') % str(e))

    def _parse_excel(self, file_content, file_ext):
        """Parsea un archivo Excel"""
        try:
            workbook = xlrd.open_workbook(file_contents=file_content)
            sheet = workbook.sheet_by_index(0)
            
            # Leer encabezados de la primera fila
            headers = [str(cell.value).strip() for cell in sheet.row(0)]
            
            lines = []
            for row_idx in range(1, sheet.nrows):
                row_data = {}
                for col_idx, header in enumerate(headers):
                    cell = sheet.cell(row_idx, col_idx)
                    value = cell.value
                    # Convertir números a string si es necesario
                    if isinstance(value, (int, float)):
                        value = str(value)
                    row_data[header] = value.strip() if value else ''
                
                if any(row_data.values()):  # Solo agregar si tiene datos
                    lines.append(row_data)
            
            return lines
        except Exception as e:
            raise ValidationError(_('Error al leer el archivo Excel: %s') % str(e))

    def _create_purchase_line(self, line_data, row_number):
        """Crea una línea de compra desde los datos del archivo"""
        # Normalizar nombres de columnas (case insensitive)
        line_data_lower = {k.lower().strip(): v for k, v in line_data.items()}
        
        # Obtener el producto
        product = self._get_product(line_data_lower, row_number)
        
        # Obtener cantidad
        quantity = self._get_quantity(line_data_lower, row_number)
        
        # Preparar valores para la línea
        line_vals = {
            'order_id': self.purchase_order_id.id,
            'product_id': product.id,
            'product_qty': quantity,
            'is_imported_line': True,
        }
        
        # Obtener UOM
        if self.product_details_option in ('file', 'pricelist'):
            uom = self._get_uom(line_data_lower, product, row_number)
            if uom:
                line_vals['product_uom'] = uom.id
        
        # Obtener precio
        if self.product_details_option in ('file', 'pricelist'):
            price = self._get_price(line_data_lower, product, row_number)
            if price is not None:
                line_vals['price_unit'] = price
        
        # Obtener descripción
        description = self._get_description(line_data_lower, product, row_number)
        if description:
            line_vals['name'] = description
        
        # Obtener impuestos
        if self.product_details_option == 'file':
            taxes = self._get_taxes(line_data_lower, product, row_number)
            if taxes:
                line_vals['taxes_id'] = [(6, 0, taxes.ids)]
        
        # Crear la línea
        self.env['purchase.order.line'].create(line_vals)
        
        return True

    def _get_product(self, line_data, row_number):
        """Obtiene el producto según el método seleccionado"""
        search_field = None
        search_value = None
        
        if self.import_product_by == 'code':
            search_field = 'default_code'
            search_value = line_data.get('product', '').strip() or line_data.get('code', '').strip()
        elif self.import_product_by == 'barcode':
            search_field = 'barcode'
            search_value = line_data.get('product', '').strip() or line_data.get('barcode', '').strip()
        else:  # name
            search_field = 'name'
            search_value = line_data.get('product', '').strip() or line_data.get('name', '').strip()
        
        if not search_value:
            raise ValidationError(_('No se encontró el valor del producto en la fila.'))
        
        # Buscar producto
        domain = [(search_field, '=', search_value)]
        product = self.env['product.product'].search(domain, limit=1)
        
        if not product:
            # Si no existe y está permitido crear, crear el producto
            if self.create_product_if_not_found and self.import_product_by == 'name':
                product = self.env['product.product'].create({
                    'name': search_value,
                    'type': 'product',
                })
            else:
                raise ValidationError(_('Producto no encontrado: %s') % search_value)
        
        return product

    def _get_quantity(self, line_data, row_number):
        """Obtiene la cantidad"""
        qty_str = line_data.get('quantity', '').strip() or line_data.get('qty', '').strip()
        if not qty_str:
            raise ValidationError(_('La cantidad es obligatoria.'))
        
        try:
            quantity = float(qty_str)
            if quantity <= 0:
                raise ValidationError(_('La cantidad debe ser mayor a cero.'))
            return quantity
        except ValueError:
            raise ValidationError(_('La cantidad debe ser un número válido.'))

    def _get_uom(self, line_data, product, row_number):
        """Obtiene la unidad de medida"""
        uom_name = line_data.get('uom', '').strip() or line_data.get('unit', '').strip()
        
        if not uom_name:
            return product.uom_po_id or product.uom_id
        
        # Buscar UOM por nombre
        uom = self.env['uom.uom'].search([
            ('name', '=', uom_name)
        ], limit=1)
        
        if not uom:
            raise ValidationError(_('Unidad de medida no encontrada: %s') % uom_name)
        
        return uom

    def _get_price(self, line_data, product, row_number):
        """Obtiene el precio"""
        price_str = line_data.get('price', '').strip() or line_data.get('price_unit', '').strip()
        
        if not price_str:
            if self.product_details_option == 'pricelist':
                # Obtener precio de la lista de precios del proveedor
                supplier_info = self.env['product.supplierinfo'].search([
                    ('product_tmpl_id', '=', product.product_tmpl_id.id),
                    ('name', '=', self.purchase_order_id.partner_id.id),
                ], limit=1)
                if supplier_info:
                    return supplier_info.price
            return None
        
        try:
            price = float(price_str)
            if price < 0:
                raise ValidationError(_('El precio no puede ser negativo.'))
            return price
        except ValueError:
            raise ValidationError(_('El precio debe ser un número válido.'))

    def _get_description(self, line_data, product, row_number):
        """Obtiene la descripción"""
        description = line_data.get('description', '').strip()
        
        if not description:
            return product.display_name
        
        return description

    def _get_taxes(self, line_data, product, row_number):
        """Obtiene los impuestos"""
        tax_names = line_data.get('tax', '').strip() or line_data.get('taxes', '').strip()
        
        if not tax_names:
            return product.supplier_taxes_id
        
        # Buscar impuestos por nombre (separados por coma)
        tax_list = [t.strip() for t in tax_names.split(',')]
        taxes = self.env['account.tax']
        
        for tax_name in tax_list:
            tax = self.env['account.tax'].search([
                ('name', 'ilike', tax_name),
                ('type_tax_use', '=', 'purchase'),
            ], limit=1)
            if tax:
                taxes |= tax
        
        if not taxes:
            raise ValidationError(_('Impuesto no encontrado: %s') % tax_names)
        
        return taxes

