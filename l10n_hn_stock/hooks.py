# -*- coding: utf-8 -*-

# Limpia relaciones campo→grupo heredadas de versiones que ponían groups= en el modelo.
# La visibilidad de coste/margen sigue en las vistas (groups en XML).

CLEAR_MARGIN_FIELD_GROUP_REL_SQL = """
    DELETE FROM ir_model_fields_group_rel AS rel
    USING ir_model_fields AS f
    WHERE rel.field_id = f.id
      AND f.model IN ('sale.order', 'sale.order.line', 'sale.report', 'account.invoice.report')
      AND f.name IN ('margin', 'margin_percent', 'purchase_price', 'price_margin')
"""


def post_init_hook(env):
    # SQL-JUSTIFIED: limpieza puntual de ir_model_fields_group_rel en post-init (sin ORM estable).
    env.cr.execute(CLEAR_MARGIN_FIELD_GROUP_REL_SQL)
