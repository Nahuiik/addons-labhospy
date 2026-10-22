from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError


class City(models.Model):
    _inherit = 'res.city'

    zip_ids = fields.One2many('res.city.zip', 'city_id',
                              string="Zips in this city")
    @api.constrains('name', 'state_id', 'country_id')
    def _check_unique_city_name(self):
        for rec in self:
            if not rec.name or not rec.state_id or not rec.country_id:
                continue
            if self.search_count([
                ('name', '=', rec.name),
                ('state_id', '=', rec.state_id.id),
                ('country_id', '=', rec.country_id.id),
                ('id', '!=', rec.id)
            ]) > 0:
                raise ValidationError('Ya existe una ciudad con ese nombre en el mismo estado. '
                                     'El nombre de la ciudad debe ser único dentro de su estado y país.')
