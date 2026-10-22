from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError


class ResCityZip(models.Model):
    """City/locations completion object"""

    _name = "res.city.zip"
    _description = __doc__
    _order = "name asc"
    _rec_name = "display_name"

    name = fields.Char('ZIP', required=True)
    city_id = fields.Many2one(
        'res.city',
        'City',
        required=True,
    )
    display_name = fields.Char(compute='_compute_new_display_name', store=True, index=True)

    @api.constrains('name', 'city_id')
    def _check_unique_zip_code(self):
        for rec in self:
            if not rec.name or not rec.city_id:
                continue
            if self.search_count([
                ('name', '=', rec.name),
                ('city_id', '=', rec.city_id.id),
                ('id', '!=', rec.id)
            ]) > 0:
                raise ValidationError('Ya existe un código postal con ese código en la misma ciudad. '
                                      'El código postal debe ser único dentro de su ciudad.')

    @api.depends('name', 'city_id')
    def _compute_new_display_name(self):
        for rec in self:
            name = [rec.name, rec.city_id.name]
            if rec.city_id.state_id:
                name.append(rec.city_id.state_id.name)
            if rec.city_id.country_id:
                name.append(rec.city_id.country_id.name)
            rec.display_name = ", ".join(name)
