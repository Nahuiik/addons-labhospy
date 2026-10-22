# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ApplyBenefitTemplateWizard(models.TransientModel):
    _name = "l10n.hn.contract.template.wizard"
    _description = "Wizard para aplicar plantilla de beneficios"

    contract_id = fields.Many2one(
        "hr.version",
        string="Contrato",
        required=True,
        default=lambda self: self.env.context.get("default_contract_id"),
    )
    template_ids = fields.Many2many(
        "l10n.hn.contract.benefit.template",
        relation="l10n_hn_contract_template_wiz_rel",
        column1="wizard_id",
        column2="template_id",
        string="Plantillas de Beneficios",
        required=True,
        domain="[('structure_type_id', '=', structure_type_id)]",
    )
    structure_type_id = fields.Many2one(
        "hr.payroll.structure.type",
        string="Tipo de Estructura",
        compute="_compute_structure_type_id",
        readonly=True,
    )

    @api.depends("contract_id")
    def _compute_structure_type_id(self):
        for wizard in self:
            if wizard.contract_id:
                wizard.structure_type_id = wizard.contract_id._get_structure_type_id()
            else:
                wizard.structure_type_id = False
    replace_existing = fields.Boolean(
        string="Reemplazar beneficios existentes",
        default=False,
        help="Si está activo, reemplazará los beneficios existentes que coincidan con los códigos de la plantilla.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Validar que siempre se proporcione contract_id."""
        for vals in vals_list:
            if not vals.get('contract_id') and not self.env.context.get('default_contract_id'):
                raise ValidationError(_("El contrato es requerido para crear el wizard."))
            if not vals.get('contract_id'):
                vals['contract_id'] = self.env.context.get('default_contract_id')
        return super().create(vals_list)

    def action_apply_templates(self):
        """Aplicar las plantillas seleccionadas al contrato."""
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("Debe seleccionar un contrato."))
        if not self.template_ids:
            raise UserError(_("Debe seleccionar al menos una plantilla."))

        contract = self.contract_id
        commands = []
        
        for template in self.template_ids:
            # Verificar si ya existe un beneficio con este código
            existing_benefit = contract.benefit_line_ids.filtered(
                lambda b: b.code == template.code or b.template_id == template
            )
            
            if existing_benefit and self.replace_existing:
                # Actualizar el existente
                existing_benefit.write(contract._prepare_benefit_line_vals(template))
            elif not existing_benefit:
                # Crear nuevo
                commands.append((0, 0, contract._prepare_benefit_line_vals(template)))
        
        if commands:
            contract.benefit_line_ids = commands

        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.version",
            "view_mode": "form",
            "res_id": contract.id,
            "target": "current",
        }

