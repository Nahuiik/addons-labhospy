from odoo import api, models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    legacy_tag_ids = fields.Many2many(
        comodel_name='product.tag',
        string='Legacy Tags',
        compute='_compute_legacy_tags',
        inverse='_inverse_legacy_tags',
        search='_search_legacy_tags',
        readonly=False,
    )

    @api.depends('product_tag_ids', 'product_tag_ids.product_template_ids')
    def _compute_legacy_tags(self):
        for template in self:
            template.legacy_tag_ids = template.product_tag_ids

    def _inverse_legacy_tags(self):
        for template in self:
            template.product_tag_ids = template.legacy_tag_ids

    def _search_legacy_tags(self, operator, value):
        return [('product_tag_ids', operator, value)]
