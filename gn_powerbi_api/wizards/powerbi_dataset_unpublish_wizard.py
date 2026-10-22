# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PowerBiDatasetUnpublishWizard(models.TransientModel):
    _name = 'powerbi.dataset.unpublish.wizard'
    _description = 'Wizard para Despublicar Dataset de Power BI'

    dataset_id = fields.Many2one(
        'powerbi.dataset',
        string='Dataset',
        required=True,
        readonly=True,
    )
    dataset_name = fields.Char(
        related='dataset_id.name',
        string='Nombre del Dataset',
        readonly=True,
    )
    delete_in_powerbi = fields.Boolean(
        string='Eliminar Dataset en Power BI',
        default=False,
        help='Si está marcado, el dataset será eliminado completamente de Power BI. '
             'Si no está marcado, solo se despublicará localmente pero el dataset permanecerá en Power BI.'
    )
    warning_message = fields.Html(
        string='Advertencia',
        compute='_compute_warning_message',
        readonly=True,
    )

    @api.depends('delete_in_powerbi')
    def _compute_warning_message(self):
        for record in self:
            if record.delete_in_powerbi:
                record.warning_message = _(
                    '<div class="alert alert-danger" role="alert">'
                    '<strong>¡Advertencia!</strong><br/>'
                    'El dataset será <strong>eliminado permanentemente</strong> de Power BI. '
                    'Esta acción no se puede deshacer. Todos los datos y reportes asociados se perderán.'
                    '</div>'
                )
            else:
                record.warning_message = _(
                    '<div class="alert alert-info" role="alert">'
                    'El dataset será despublicado localmente pero <strong>permanecerá en Power BI</strong>. '
                    'Podrás volver a publicarlo más tarde vinculándolo nuevamente.'
                    '</div>'
                )

    def action_confirm(self):
        """
        Confirma la despublicación del dataset
        """
        self.ensure_one()
        
        if not self.dataset_id:
            raise UserError(_('Debe seleccionar un dataset'))

        # Llamar al método de despublicación
        self.dataset_id.action_unpublish(delete_in_powerbi=self.delete_in_powerbi)
        
        return {
            'type': 'ir.actions.act_window_close',
        }

