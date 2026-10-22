# -*- coding: utf-8 -*-
from odoo import models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    def get_current_warehouses(self):
        """Incluye sucursal para el panel de Existencias (multi-almacén / filtro sucursal)."""
        fields_list = ['id', 'name', 'code']
        if 'branch_id' in self._fields:
            fields_list.append('branch_id')
        return self.env['stock.warehouse'].search_read(fields=fields_list)
