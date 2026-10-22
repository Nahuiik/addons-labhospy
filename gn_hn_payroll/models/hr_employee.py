from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    salary_input_ids = fields.One2many(
        "hr.employee.salary.input",
        "employee_id",
        string="Beneficios y deducciones",
        groups="hr_payroll.group_hr_payroll_user",
    )
    ihss_config_id = fields.Many2one(
        "hr.ihss.settings",
        compute="_compute_ihss_config_fields",
        string="Deducción IHSS",
        readonly=True,
    )
    ihss_total_fee = fields.Float(
        compute="_compute_ihss_config_fields",
        string="Cuota de seguro",
        readonly=True,
        digits=(12, 2),
    )
    ihss_ivm_fee = fields.Float(
        compute="_compute_ihss_config_fields",
        string="Cuota IVM",
        readonly=True,
        digits=(12, 2),
    )
    ihss_enf_mat_fee = fields.Float(
        compute="_compute_ihss_config_fields",
        string="Cuota ENF-MAT",
        readonly=True,
        digits=(12, 2),
    )
    ihss_manual = fields.Boolean(string="IHSS manual")
    afp_config_id = fields.Many2one(
        "hr.afp.settings",
        compute="_compute_afp_config_fields",
        string="Deducción AFP",
        readonly=True,
    )
    afp_quincena_amount = fields.Float(
        compute="_compute_afp_config_fields",
        string="Cuota de AFP",
        readonly=True,
        digits=(12, 2),
    )
    afp_manual = fields.Boolean(string="AFP manual")

    @api.depends_context("company_id")
    def _compute_ihss_config_fields(self):
        IhssSettings = self.env["hr.ihss.settings"]
        validated_settings = IhssSettings.search(
            [("state", "=", "validated")], order="create_date desc", limit=1
        )
        for employee in self:
            employee.ihss_config_id = validated_settings
            if validated_settings:
                employee.ihss_total_fee = validated_settings.ihss_fee or 0.0
                employee.ihss_ivm_fee = validated_settings.ivm_fee or 0.0
                employee.ihss_enf_mat_fee = validated_settings.enf_mat_fee or 0.0
            else:
                employee.ihss_total_fee = 0.0
                employee.ihss_ivm_fee = 0.0
                employee.ihss_enf_mat_fee = 0.0

    @api.depends("company_id")
    def _compute_afp_config_fields(self):
        AfpSettings = self.env["hr.afp.settings"]
        settings_cache = {}
        for employee in self:
            company = employee.company_id
            cache_key = company.id if company else False
            if cache_key not in settings_cache:
                domain = [("state", "=", "validated")]
                if company:
                    domain.append(("company_id", "=", company.id))
                settings_cache[cache_key] = AfpSettings.search(
                    domain, order="create_date desc", limit=1
                )
            settings = settings_cache.get(cache_key)
            employee.afp_config_id = settings
            amount = 0.0
            if settings:
                lines_by_employee = {
                    line.employee_id.id: line for line in settings.line_ids
                }
                line = lines_by_employee.get(employee.id)
                if line:
                    amount = line.quincena_amount or line.afp_amount or 0.0
            employee.afp_quincena_amount = amount
