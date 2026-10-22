# -*- coding: utf-8 -*-
"""Grant read-only ir.model.access on Elite Architects Appendix A models."""

EA_API_MODELS = [
    'res.partner',
    'res.partner.category',
    'sale.order',
    'sale.order.line',
    'crm.team',
    'sale.report',
    'crm.lead',
    'crm.stage',
    'crm.lost.reason',
    'product.template',
    'product.product',
    'product.category',
    'product.pricelist',
    'product.pricelist.item',
    'uom.uom',
    'stock.quant',
    'stock.warehouse',
    'stock.location',
    'stock.picking',
    'stock.move',
    'purchase.order',
    'purchase.order.line',
    'account.move',
    'account.move.line',
    'account.payment',
    'account.payment.term',
    'account.payment.term.line',
    'account.invoice.report',
    'account.journal',
    'account.account',
    'account.bank.statement',
    'account.bank.statement.line',
    'res.currency',
    'res.currency.rate',
    'mail.activity',
    'mail.activity.type',
    'mail.message',
    'res.company',
    'res.users',
]


def post_init_hook(env):
    group = env.ref('gn_labhospy_ea_api.group_labhospy_ea_api_readonly', raise_if_not_found=False)
    if not group:
        return
    Access = env['ir.model.access'].sudo()
    for model_name in EA_API_MODELS:
        model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not model:
            continue
        xmlid = f'access_ea_api_read_{model_name.replace(".", "_")}'
        existing = env.ref(f'gn_labhospy_ea_api.{xmlid}', raise_if_not_found=False)
        if existing:
            continue
        access = Access.create({
            'name': f'EA API read {model_name}',
            'model_id': model.id,
            'group_id': group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_create': False,
            'perm_unlink': False,
        })
        env['ir.model.data'].sudo().create({
            'module': 'gn_labhospy_ea_api',
            'name': xmlid,
            'model': 'ir.model.access',
            'res_id': access.id,
            'noupdate': True,
        })
