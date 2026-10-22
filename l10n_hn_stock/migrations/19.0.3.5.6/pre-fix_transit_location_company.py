# -*- coding: utf-8 -*-
# Asignar compañía a la ubicación de tránsito creada sin company_id.
# El ORM de stock.location prohíbe pasar de sin compañía a con compañía en write();
# este paso SQL evita el error al actualizar el módulo y alinea con stock_account.


def migrate(cr, version):
    cr.execute(
        """
        UPDATE stock_location AS sl
        SET company_id = sub.first_company_id
        FROM ir_model_data AS imd,
             (SELECT id AS first_company_id FROM res_company ORDER BY id LIMIT 1) AS sub
        WHERE imd.model = 'stock.location'
          AND imd.module = 'l10n_hn_stock'
          AND imd.name = 'stock_location_inter_store_transit'
          AND imd.res_id = sl.id
          AND sl.company_id IS NULL
        """
    )
