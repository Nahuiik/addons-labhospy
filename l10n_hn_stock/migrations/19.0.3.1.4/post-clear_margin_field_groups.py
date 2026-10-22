# -*- coding: utf-8 -*-


def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_model_fields_group_rel AS rel
        USING ir_model_fields AS f
        WHERE rel.field_id = f.id
          AND f.model IN ('sale.order', 'sale.order.line', 'sale.report', 'account.invoice.report')
          AND f.name IN ('margin', 'margin_percent', 'purchase_price', 'price_margin')
        """
    )
